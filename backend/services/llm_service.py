import mlx_lm
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
        # We will lazy-load models to save massive amounts of RAM and prevent OS swapping!
        self.active_model_name = None
        self.active_model_data = None
        self.model_paths = {
            "standard": "/Users/abhinavkumarsingh/ENO/mlx_models/gemma-2-2b-it-4bit",
            "bro": "/Users/abhinavkumarsingh/ENO/qwen_local_weights"
        }

    def _get_model(self, model_type: str):
        if self.active_model_name == model_type and self.active_model_data:
            return self.active_model_data

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

    async def stream_generate(self, prompt: str, max_tokens: int = 512, temp: float = 0.7, model_type: str = "standard") -> AsyncGenerator[str, None]:
        if model_type not in self.model_paths:
            # Fallback to standard
            model_type = "standard"
            
        model_data = self._get_model(model_type)
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
        
        gen = mlx_stream_generate(
            target_model, 
            target_tokenizer, 
            prompt, 
            max_tokens=max_tokens
        )

        for res in gen:
            token_id = res.token
            if token_id in stop_ids:
                break

            text_chunk = res.text
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

llm_service = LLMService()
