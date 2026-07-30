from huggingface_hub import snapshot_download
import sys

print("Forcing direct download of BAAI/bge-small-en-v1.5...")
try:
    path = snapshot_download(
        repo_id="BAAI/bge-small-en-v1.5",
        local_dir_use_symlinks=False
    )
    print(f"Download complete! Saved to {path}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
