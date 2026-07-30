import mlx_lm
import sys
import time

print("Booting Qwen into Mac Unified Memory...")
start = time.time()
local_path = "/Volumes/AbhinavsD/ENO/qwen_local_weights"

try:
    model, tokenizer = mlx_lm.load(local_path)
    print(f"\n✅ Model loaded successfully in {time.time() - start:.2f} seconds!")
    
    prompt_text = "System: You are Eno. Student: Are you ready to teach? Eno:"
    print(f"\nAsking Eno: '{prompt_text}'...")
    response = mlx_lm.generate(model, tokenizer, prompt=prompt_text, max_tokens=20, verbose=False)
    print("\nEno's Response:\n" + response)
except Exception as e:
    print(f"FAILED TO LOAD MODEL: {e}")
    sys.exit(1)
