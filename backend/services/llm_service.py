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

        tokens_generated = 0
        current_text = ""

        # Using the highly optimized stream_generate from newer MLX versions
        from mlx_lm import stream_generate as mlx_stream_generate
        
        gen = mlx_stream_generate(
            target_model, 
            target_tokenizer, 
            prompt, 
            max_tokens=max_tokens, 
            temp=temp
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
