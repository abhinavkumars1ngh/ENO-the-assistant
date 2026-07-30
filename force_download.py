from huggingface_hub import snapshot_download
import sys

print("Forcing direct download of Qwen MLX weights...")
try:
    path = snapshot_download(
        repo_id="mlx-community/Qwen2.5-7B-Instruct-4bit",
        allow_patterns=["*.safetensors", "*.json", "*.txt"],
        local_dir="./qwen_local_weights",
        local_dir_use_symlinks=False
    )
    print(f"Download complete! Saved to {path}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
