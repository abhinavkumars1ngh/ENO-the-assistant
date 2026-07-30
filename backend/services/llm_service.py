import mlx_lm
from mlx_lm.utils import generate_step
import mlx.core as mx
import asyncio
from typing import AsyncGenerator

MODEL_PATH = "mlx-community/gemma-2-2b-it"

# Patterns that indicate the model is hallucinating a new turn
STOP_PATTERNS = [
    "\nuser:", "\nUser:", "\nuser :",
    "\nEno:", "\neno:", "\nassistant:", "\nAssistant:",
    "<|im_start|>", "<|im_end|>", "<|endoftext|>",
    "<eos>", "<end_of_turn>", "<end_of_turn", "<start_of_turn>", "<start_of_turn"
]

class LLMService:
    def __init__(self):
        self.models = {}
        
        # 1. Load Gemma (Standard)
        try:
            print("Loading Standard MLX model: mlx_models/gemma-2-2b-it-4bit")
            m_gemma, t_gemma = mlx_lm.load("/Users/abhinavkumarsingh/ENO/mlx_models/gemma-2-2b-it-4bit")
            
            # Collect stop tokens for Gemma
            stop_ids_gemma = set()
            for special in ["<|im_end|>", "<|im_start|>", "<|endoftext|>", "<eos>", "<end_of_turn>"]:
                ids = t_gemma.encode(special, add_special_tokens=False)
                stop_ids_gemma.update(ids)
            if hasattr(t_gemma, 'eos_token_id') and t_gemma.eos_token_id is not None:
                stop_ids_gemma.add(t_gemma.eos_token_id)
                
            self.models["standard"] = {
                "model": m_gemma,
                "tokenizer": t_gemma,
                "stop_token_ids": stop_ids_gemma
            }
            print("Standard (Gemma) model loaded!")
        except Exception as e:
            print(f"Failed to load Gemma: {e}")
            
        # 2. Load Qwen (Bro)
        try:
            print("Loading Bro MLX model: /Users/abhinavkumarsingh/ENO/qwen_local_weights")
            m_qwen, t_qwen = mlx_lm.load("/Users/abhinavkumarsingh/ENO/qwen_local_weights")
            
            # Collect stop tokens for Qwen
            stop_ids_qwen = set()
            for special in ["<|im_end|>", "<|im_start|>", "<|endoftext|>"]:
                ids = t_qwen.encode(special, add_special_tokens=False)
                stop_ids_qwen.update(ids)
            if hasattr(t_qwen, 'eos_token_id') and t_qwen.eos_token_id is not None:
                stop_ids_qwen.add(t_qwen.eos_token_id)
                
            self.models["bro"] = {
                "model": m_qwen,
                "tokenizer": t_qwen,
                "stop_token_ids": stop_ids_qwen
            }
            print("Bro (Qwen) model loaded!")
        except Exception as e:
            print(f"Failed to load Qwen: {e}")

    async def stream_generate(self, prompt: str, max_tokens: int = 512, temp: float = 0.7, model_type: str = "standard") -> AsyncGenerator[str, None]:
        if model_type not in self.models:
            # Fallback to whatever is available
            available = list(self.models.keys())
            if not available:
                yield "I am offline. No models could be loaded."
                return
            model_type = available[0]
            
        target_model = self.models[model_type]["model"]
        target_tokenizer = self.models[model_type]["tokenizer"]
        stop_ids = self.models[model_type]["stop_token_ids"]

        # Tokenize the prompt
        inputs = target_tokenizer.encode(prompt, return_tensors="np")
        prompt_tokens = mx.array(inputs[0])

        tokens_generated = 0
        all_token_ids: list[int] = []  # Accumulate all generated token IDs
        prev_decoded_len = 0           # Character count already yielded

        for (token, prob) in generate_step(prompt_tokens, target_model, temp=temp):
            if tokens_generated >= max_tokens:
                break

            token_id = token if isinstance(token, int) else token.item()

            # Stop on any special stop token
            if token_id in stop_ids:
                break

            all_token_ids.append(token_id)

            # Decode ALL tokens together in one call.
            # This is the CORRECT way to handle multi-token Unicode characters
            # (e.g. emoji like 🔥 split across Qwen's byte-fallback BPE tokens).
            # Decoding a full sequence lets the tokenizer stitch byte tokens properly.
            try:
                current_text = target_tokenizer.decode(all_token_ids, skip_special_tokens=False)
            except Exception:
                tokens_generated += 1
                await asyncio.sleep(0)
                continue

            # New text since last yield
            new_chunk = current_text[prev_decoded_len:]

            # If the decoded text ends with a replacement character (U+FFFD),
            # it means we have an incomplete multi-byte UTF-8 sequence (like an emoji).
            # We skip yielding and hold the buffer until the next token completes the character.
            if not new_chunk or current_text.endswith('\ufffd'):
                tokens_generated += 1
                await asyncio.sleep(0)
                continue

            # Check for stop patterns in the full decoded text
            should_stop = False
            for pattern in STOP_PATTERNS:
                if pattern in current_text:
                    # Only yield up to the stop pattern
                    stop_idx = current_text.index(pattern)
                    clean_chunk = current_text[prev_decoded_len:stop_idx]
                    if clean_chunk:
                        yield clean_chunk
                    should_stop = True
                    break

            if should_stop:
                break

            yield new_chunk
            prev_decoded_len = len(current_text)

            tokens_generated += 1
            await asyncio.sleep(0)  # Yield to event loop

llm_service = LLMService()
