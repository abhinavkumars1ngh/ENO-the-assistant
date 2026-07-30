import mlx_lm
import sys
import time

print("Booting model into memory...")
start = time.time()
try:
    model, tokenizer = mlx_lm.load("mlx-community/Qwen2.5-7B-Instruct-4bit")
    print(f"Model loaded successfully in {time.time() - start:.2f} seconds!")
    
    print("Generating test response...")
    response = mlx_lm.generate(model, tokenizer, prompt="Are you ready?", max_tokens=10, verbose=True)
    print("Response:", response)
except Exception as e:
    print(f"FAILED TO LOAD MODEL: {e}")
    sys.exit(1)
