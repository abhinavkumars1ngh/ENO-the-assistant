import mlx_lm
import sys

MODEL_REPO = "mlx-community/Qwen2.5-7B-Instruct-4bit"

def install_and_test_ai():
    print(f"Downloading and loading MLX model: {MODEL_REPO}")
    print("This might take a while depending on your internet connection (approx 4-5 GB).")
    try:
        model, tokenizer = mlx_lm.load(MODEL_REPO)
        print("Model loaded successfully into MLX!")
        
        prompt = "Hello Eno! Are you ready to teach?"
        print(f"\nTesting generation with prompt: '{prompt}'")
        
        # Test a quick generation
        response = mlx_lm.generate(model, tokenizer, prompt=prompt, max_tokens=50, verbose=True)
        print("\nAI test generation complete.")
        
    except Exception as e:
        print(f"Failed to install/load AI model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    install_and_test_ai()
