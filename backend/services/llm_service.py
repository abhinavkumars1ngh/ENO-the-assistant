import re
import asyncio
import json
from typing import AsyncGenerator, Optional

from backend.core import config

# MLX is imported lazily (inside the local path) because it only exists on Apple Silicon.
# Importing it at module load made the backend impossible to boot on Linux hosts.

# Patterns that indicate the model is hallucinating a new turn
STOP_PATTERNS = [
    "\nuser:", "\nUser:", "\nuser :",
    "\nEno:", "\neno:", "\nassistant:", "\nAssistant:",
    "<|im_start|>", "<|im_end|>", "<|endoftext|>",
    "<eos>", "<end_of_turn>", "<end_of_turn", "<start_of_turn>", "<start_of_turn"
]

_THINK_OPEN, _THINK_CLOSE = "<think>", "</think>"


class _ThinkStripper:
    """Streaming filter that drops <think>...</think> blocks emitted by reasoning models."""

    def __init__(self):
        self.in_think = False
        self.pending = ""

    def feed(self, text: str) -> str:
        self.pending += text
        out = ""
        while True:
            if self.in_think:
                idx = self.pending.find(_THINK_CLOSE)
                if idx == -1:
                    # keep only a possible partial closing tag
                    keep = len(_THINK_CLOSE) - 1
                    self.pending = self.pending[-keep:] if len(self.pending) > keep else self.pending
                    return out
                self.pending = self.pending[idx + len(_THINK_CLOSE):].lstrip("\n")
                self.in_think = False
            else:
                idx = self.pending.find(_THINK_OPEN)
                if idx != -1:
                    out += self.pending[:idx]
                    self.pending = self.pending[idx + len(_THINK_OPEN):]
                    self.in_think = True
                    continue
                # hold back a trailing partial "<think>" prefix
                hold = 0
                for n in range(min(len(_THINK_OPEN) - 1, len(self.pending)), 0, -1):
                    if _THINK_OPEN.startswith(self.pending[-n:]):
                        hold = n
                        break
                if hold:
                    out += self.pending[:-hold]
                    self.pending = self.pending[-hold:]
                else:
                    out += self.pending
                    self.pending = ""
                return out

    def flush(self) -> str:
        tail = "" if self.in_think else self.pending
        self.pending = ""
        return tail


class LLMService:
    def __init__(self):
        # We will lazy-load models to save massive amounts of RAM and prevent OS swapping!
        self.active_model_name = None
        self.active_model_data = None
        self.model_paths = {
            "standard": str(config.PROJECT_ROOT / "mlx_models" / "gemma-2-2b-it-4bit"),
            "bro": str(config.PROJECT_ROOT / "qwen_local_weights"),
        }
        # Global lock to prevent concurrent generations from OOMing the Mac or corrupting KV cache
        self.generation_lock = asyncio.Lock()

    # ------------------------------------------------------------------ MLX
    def _get_model(self, model_type: str):
        if self.active_model_name == model_type and self.active_model_data:
            return self.active_model_data

        import mlx_lm  # local-only dependency

        # Unload the old model from GPU memory to prevent Apple Silicon from swapping
        if self.active_model_data is not None:
            print(f"Unloading model {self.active_model_name} from memory...")
            del self.active_model_data
            self.active_model_data = None
            self.active_model_name = None
            import gc
            gc.collect()

        print(f"Loading MLX model ({model_type}): {self.model_paths[model_type]}")
        try:
            m, t = mlx_lm.load(self.model_paths[model_type])

            # Collect stop tokens
            stop_ids = set()
            for special in ["<|im_end|>", "<|im_start|>", "<|endoftext|>", "<eos>", "<end_of_turn>"]:
                ids = t.encode(special, add_special_tokens=False)
                stop_ids.update(ids)
            if hasattr(t, 'eos_token_id') and t.eos_token_id is not None:
                stop_ids.add(t.eos_token_id)

            self.active_model_data = {
                "model": m,
                "tokenizer": t,
                "stop_token_ids": stop_ids
            }
            self.active_model_name = model_type
            print(f"{model_type.capitalize()} model loaded successfully!")
            return self.active_model_data
        except Exception as e:
            print(f"Failed to load {model_type}: {e}")
            return None

    async def _stream_mlx(self, prompt: str, max_tokens: int, model_type: str) -> AsyncGenerator[str, None]:
        async with self.generation_lock:
            if model_type not in self.model_paths:
                # Fallback to standard
                model_type = "standard"

            try:
                model_data = self._get_model(model_type)
            except ImportError:
                model_data = None
            if not model_data:
                yield "I am offline. The model failed to load."
                return

            target_model = model_data["model"]
            target_tokenizer = model_data["tokenizer"]
            stop_ids = model_data["stop_token_ids"]

            tokens_generated = 0
            current_text = ""

            # Using the highly optimized stream_generate from newer MLX versions
            from mlx_lm import stream_generate as mlx_stream_generate
            import mlx_lm.sample_utils as su

            try:
                sampler = su.make_sampler(temp=0.75, repetition_penalty=1.1, repetition_context_size=100)
            except Exception:
                sampler = su.make_sampler(temp=0.75)

            gen = mlx_stream_generate(
                target_model,
                target_tokenizer,
                prompt,
                max_tokens=max_tokens,
                sampler=sampler
            )

            for res in gen:
                token_id = res.token
                if token_id in stop_ids:
                    break

                text_chunk = res.text

                # ABORT ON MANDARIN: If the model starts hallucinating Chinese characters, kill it instantly
                if re.search(r'[一-鿿]', text_chunk):
                    break

                current_text += text_chunk

                should_stop = False
                for pattern in STOP_PATTERNS:
                    # If a stop pattern is detected in the latest text, break
                    if pattern in current_text[-50:]:
                        # Don't yield the chunk that contains the stop pattern
                        should_stop = True
                        break

                if should_stop:
                    break

                yield text_chunk
                tokens_generated += 1

                # Yield to event loop occasionally to prevent blocking FastAPI
                if tokens_generated % 4 == 0:
                    await asyncio.sleep(0)

    # --------------------------------------------------- OpenAI-compatible
    def remote_model_name(self, model_type: str) -> str:
        return config.LLM_MODEL_BRO if model_type == "bro" else config.LLM_MODEL_STANDARD

    async def _stream_openai(
        self, messages: list[dict], max_tokens: int, temp: float, model_type: str
    ) -> AsyncGenerator[str, None]:
        import httpx

        model_name = self.remote_model_name(model_type)
        if not config.LLM_BASE_URL or not model_name:
            print("LLM_BASE_URL / LLM_MODEL_* not configured for the openai backend.")
            yield "The model endpoint is not configured on this server."
            return

        headers = {"Content-Type": "application/json"}
        if config.LLM_API_KEY:
            headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": True,
            "temperature": temp,
            "max_tokens": min(max_tokens, config.LLM_MAX_TOKENS),
        }

        stripper = _ThinkStripper()
        timeout = httpx.Timeout(connect=10.0, read=90.0, write=20.0, pool=10.0)
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST", f"{config.LLM_BASE_URL}/chat/completions", headers=headers, json=payload
                ) as resp:
                    if resp.status_code != 200:
                        # Log the status only. Never log request/response bodies.
                        print(f"LLM endpoint returned HTTP {resp.status_code}")
                        yield "The model is temporarily unavailable. Please try again in a moment."
                        return
                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            delta = json.loads(data)["choices"][0].get("delta", {}).get("content")
                        except (ValueError, KeyError, IndexError):
                            continue
                        if not delta:
                            continue
                        cleaned = stripper.feed(delta)
                        if cleaned:
                            yield cleaned
            tail = stripper.flush()
            if tail:
                yield tail
        except httpx.HTTPError as e:
            print(f"LLM endpoint error: {type(e).__name__}")
            yield "The model is temporarily unavailable. Please try again in a moment."

    # ------------------------------------------------------------- public
    async def stream_generate(
        self,
        prompt: Optional[str] = None,
        max_tokens: int = 512,
        temp: float = 0.7,
        model_type: str = "standard",
        messages: Optional[list[dict]] = None,
    ) -> AsyncGenerator[str, None]:
        if config.LLM_BACKEND == "openai":
            async for chunk in self._stream_openai(messages or [], max_tokens, temp, model_type):
                yield chunk
        else:
            async for chunk in self._stream_mlx(prompt or "", max_tokens, model_type):
                yield chunk

llm_service = LLMService()
