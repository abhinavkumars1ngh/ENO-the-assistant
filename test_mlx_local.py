import mlx_lm
import sys
import time

print("Booting model into memory from LOCAL PATH...")
start = time.time()
local_path = "/Users/abhinavkumarsingh/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed"

try:
    model, tokenizer = mlx_lm.load(local_path)
    print(f"Model loaded successfully in {time.time() - start:.2f} seconds!")
    
    print("Generating test response...")
    response = mlx_lm.generate(model, tokenizer, prompt="Are you ready?", max_tokens=10, verbose=True)
    print("Response:", response)
except Exception as e:
    print(f"FAILED TO LOAD MODEL: {e}")
    sys.exit(1)
