import mlx_lm
import sys

print("Loading Qwen 2.5 (4-bit) into Apple Silicon Memory...")
try:
    model, tokenizer = mlx_lm.load("/Volumes/AbhinavsD/ENO/qwen_local_weights")
    prompt = "System: You are a highly intelligent AI assistant named Eno. User: What is the capital of France? Eno: "
    print("Asking Eno: 'What is the capital of France?'")
    response = mlx_lm.generate(model, tokenizer, prompt=prompt, max_tokens=20, verbose=False)
    print("\n--- ENO'S RESPONSE ---")
    print(response.strip())
    print("----------------------\n")
    print("✅ The model is 100% downloaded and working perfectly on your Mac!")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
