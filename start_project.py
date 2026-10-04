import subprocess
import signal
import sys
import time
import os

processes = []

def cleanup(signum, frame):
    print("\n[Eno AI] Shutting down all services...")
    for p in processes:
        if p.poll() is None:
            try:
                p.kill()
            except Exception:
                pass
                
    # Force kill any orphaned processes
    subprocess.run(["pkill", "-9", "-f", "cloudflared tunnel"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "ngrok http"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "caffeinate"], capture_output=True)
    subprocess.run(["pkill", "-9", "-f", "uvicorn backend.main:app"], capture_output=True)
    try:
        kill_port(8000)
        kill_port(3000)
    except NameError:
        pass # In case kill_port isn't parsed yet
        
    print("[Eno AI] Cleanup complete. Mac will now be allowed to sleep. Exiting.")
    os._exit(0)

# Register signal handlers for clean exit
signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)

def kill_port(port):
    try:
        result = subprocess.run(["lsof", "-ti", f":{port}"], capture_output=True, text=True)
        pids = result.stdout.strip().split('\n')
        for pid in pids:
            if pid:
                subprocess.run(["kill", "-9", pid])
    except Exception:
        pass

def is_docker_running():
    try:
        result = subprocess.run(["docker", "info"], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

def start_container(name, image, ports, volumes=None):
    result = subprocess.run(["docker", "ps", "-a", "-q", "-f", f"name={name}"], capture_output=True, text=True)
    if result.stdout.strip():
        subprocess.run(["docker", "start", name], capture_output=True)
    else:
        cmd = ["docker", "run", "-d", "--name", name]
        for p in ports:
            cmd.extend(["-p", p])
        if volumes:
            for v in volumes:
                cmd.extend(["-v", v])
        cmd.append(image)
        subprocess.run(cmd, capture_output=True)

def download_models(base_dir, python_bin):
    """
    Downloads the MLX models on first run if they are not cached.
    Uses huggingface_hub inside the venv to show the native progress bar.
    """
    gemma_dir = os.path.join(base_dir, "mlx_models", "gemma-2-2b-it-4bit")
    qwen_dir = os.path.join(base_dir, "qwen_local_weights")
    
    # Simple inline python script to run inside the venv so it uses the right dependencies
    dl_script = f"""
import os
from huggingface_hub import snapshot_download

gemma_dir = r"{gemma_dir}"
qwen_dir = r"{qwen_dir}"

print("\\n[Eno AI] Checking local model cache...")

if not os.path.exists(gemma_dir) or not os.listdir(gemma_dir):
    print("[Eno AI] Downloading Standard Model (Gemma-2-2B-it-4bit MLX) - This is a multi-GB download...")
    os.makedirs(gemma_dir, exist_ok=True)
    snapshot_download(repo_id="mlx-community/gemma-2-2b-it-4bit", local_dir=gemma_dir, local_dir_use_symlinks=False)
    print("[Eno AI] Standard model download complete!\\n")
else:
    print("[Eno AI] Standard model found in cache.")

if not os.path.exists(qwen_dir) or not os.listdir(qwen_dir):
    print("[Eno AI] Downloading Bro Model (Qwen2.5-1.5B-Instruct-4bit MLX)...")
    os.makedirs(qwen_dir, exist_ok=True)
    snapshot_download(repo_id="mlx-community/Qwen2.5-1.5B-Instruct-4bit", local_dir=qwen_dir, local_dir_use_symlinks=False)
    print("[Eno AI] Bro model download complete!\\n")
else:
    print("[Eno AI] Bro model found in cache.")
"""
    subprocess.run([python_bin, "-c", dl_script])

def main():
    base_dir = os.path.abspath(os.path.dirname(__file__))

    print("[Eno AI] Cleaning up existing ports (8000, 3000) and legacy tunnels...")
    kill_port(8000)
    kill_port(3000)
    subprocess.run(["pkill", "-f", "cloudflared tunnel"], capture_output=True)
    subprocess.run(["pkill", "-f", "caffeinate"], capture_output=True)
    subprocess.run(["pkill", "-f", "uvicorn backend.main:app"], capture_output=True)

    lock_file = os.path.join(base_dir, "storage", "qdrant", ".lock")
    if os.path.exists(lock_file):
        os.remove(lock_file)

    python_bin = os.path.join(base_dir, "venv312", "bin", "python")
    if not os.path.exists(python_bin):
        print("[Eno AI] Error: Virtual environment 'venv312' not found. Please run setup first.")
        sys.exit(1)

    # 1. First-run Model Download Check
    download_models(base_dir, python_bin)

    autoeck_path = os.path.join(base_dir, "autoeck.py")
    if os.path.exists(autoeck_path):
        print("[Eno AI] Starting continuous cookie updater...")
        cookie_updater = subprocess.Popen(
            [python_bin, autoeck_path],
            cwd=base_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        processes.append(cookie_updater)

    # -------------------------------------------------

    if is_docker_running():
        print("[Eno AI] Docker is running! Starting Qdrant and Redis containers...")
        start_container(
            "eno_qdrant",
            "qdrant/qdrant",
            ["6333:6333", "6334:6334"],
            [f"{os.path.join(base_dir, 'storage', 'qdrant')}:/qdrant/storage"]
        )
        start_container("eno_redis", "redis", ["6379:6379"])

        print("[Eno AI] Starting Celery worker...")
        celery = subprocess.Popen(
            [python_bin, "-m", "celery", "-A", "backend.core.celery_app", "worker", "--loglevel=info"],
            cwd=base_dir,
            env=os.environ.copy()
        )
        processes.append(celery)
        time.sleep(3)
    else:
        print("[Eno AI] Docker is skipped, running completely local (Qdrant on disk, Celery in-memory)...")

    print("[Eno AI] Starting backend API (FastAPI) and initializing MLX models on Apple Silicon...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["ENO_MODE"] = "local" # Force local mode to load MLX weights
    backend = subprocess.Popen(
        [python_bin, "-m", "uvicorn", "backend.main:app", "--port", "8000"],
        cwd=base_dir,
        env=env
    )
    processes.append(backend)

    time.sleep(5) # Give MLX time to load into GPU

    print("[Eno AI] Starting frontend (Next.js static export / dev mode)...")
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=os.path.join(base_dir, "frontend")
    )
    processes.append(frontend)

    print("[Eno AI] Starting Cloudflare Tunnel (Secure URL)...")
    cloudflared = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:8000"]
    )
    processes.append(cloudflared)

    print("[Eno AI] Running Caffeinate to prevent Mac from sleeping...")
    caffeinate = subprocess.Popen(["caffeinate", "-d"])
    processes.append(caffeinate)

    print("\n" + "=" * 60)
    print("✅ Pipeline is running! Eno AI is online locally.")
    print("🧠 Active Models: Gemma-2-2B-it (Standard) & Qwen2.5-1.5B (Bro)")
    print("Local UI: http://localhost:3000")
    print("Cloudflare Tunnel: Check the logs above for your trycloudflare.com URL!")
    print("Press Ctrl+C to safely stop the pipeline.")
    print("=" * 60 + "\n")

    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        cleanup(None, None)

if __name__ == "__main__":
    main()
