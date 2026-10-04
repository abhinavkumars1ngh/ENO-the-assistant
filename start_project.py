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

def get_host_auth_token(base_dir, python_bin):
    """Obtain or generate a valid JWT session token for the host instance owner."""
    cmd = [
        python_bin, "-c",
        """
import uuid
from backend.core.database import SessionLocal, init_db
from backend.models.schema import User
from backend.core.auth import default_token_for, set_instance_owner
init_db()
db = SessionLocal()
user = db.query(User).first()
if not user:
    user = User(email='host@local', role='user', plan='pro', public_id=uuid.uuid4().hex)
    db.add(user)
    db.commit()
    db.refresh(user)
set_instance_owner(user.id, getattr(user, 'email', ''))
print(default_token_for(user))
"""
    ]
    res = subprocess.run(cmd, cwd=base_dir, capture_output=True, text=True)
    return res.stdout.strip()


def register_endpoint_and_heartbeat(base_dir, python_bin, endpoint_url):
    """Registers the discovered Cloudflare tunnel URL and maintains a 30s heartbeat."""
    import json
    import urllib.request

    token = get_host_auth_token(base_dir, python_bin)
    if not token:
        print("[Eno Registry] ⚠️ Could not obtain host token for registration.")
        return

    api_url = "http://127.0.0.1:8000/api/register-endpoint"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # Retry up to 10 times waiting for FastAPI to finish booting
    registered = False
    for attempt in range(1, 11):
        try:
            payload = json.dumps({"endpoint_url": endpoint_url, "owner_type": "user"}).encode("utf-8")
            req = urllib.request.Request(api_url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    print(f"\n[Eno Registry] ✅ Auto-registered host endpoint: {endpoint_url} (owner_id={data.get('owner_id')})")
                    registered = True
                    break
        except Exception:
            time.sleep(1.5)

    if not registered:
        print(f"[Eno Registry] ⚠️ Could not register endpoint automatically with local backend.")
        return

    # 30-second heartbeat loop
    while True:
        time.sleep(30)
        try:
            payload = json.dumps({"owner_type": "user"}).encode("utf-8")
            req = urllib.request.Request(api_url, data=payload, headers=headers, method="PATCH")
            with urllib.request.urlopen(req, timeout=5) as resp:
                pass
        except Exception:
            pass


def main():
    base_dir = os.path.abspath(os.path.dirname(__file__))

    print("[Eno AI] Cleaning up existing ports (8000, 3000) and legacy tunnels...")
    kill_port(8000)
    kill_port(3000)
    subprocess.run(["pkill", "-f", "cloudflared tunnel"], capture_output=True)
    subprocess.run(["pkill", "-f", "caffeinate"], capture_output=True)
    subprocess.run(["pkill", "-f", "uvicorn backend.main:app"], capture_output=True)

    for lock_sub in ["qdrant_local", "qdrant"]:
        lf = os.path.join(base_dir, "storage", lock_sub, ".lock")
        if os.path.exists(lf):
            try:
                os.remove(lf)
            except OSError:
                pass

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

    print("[Eno AI] Running 100% serverless local stack (embedded Qdrant on disk, zero Docker required)...")

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
        ["cloudflared", "tunnel", "--url", "http://localhost:8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    processes.append(cloudflared)

    # Background thread to auto-capture Cloudflare URL and register to endpoint registry
    import re, threading

    def tunnel_monitor():
        tunnel_regex = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
        discovered = None
        for line in iter(cloudflared.stdout.readline, ''):
            if not line:
                break
            print(line, end="", flush=True)
            if not discovered:
                m = tunnel_regex.search(line)
                if m:
                    discovered = m.group(0)
                    print(f"\n[Eno AI] 🔗 Auto-captured Cloudflare Tunnel: {discovered}")
                    threading.Thread(
                        target=register_endpoint_and_heartbeat,
                        args=(base_dir, python_bin, discovered),
                        daemon=True
                    ).start()

    threading.Thread(target=tunnel_monitor, daemon=True).start()

    print("[Eno AI] Running Caffeinate to prevent Mac from sleeping...")
    caffeinate = subprocess.Popen(["caffeinate", "-d"])
    processes.append(caffeinate)

    print("\n" + "=" * 60)
    print("✅ Pipeline is running! Eno AI is online locally.")
    print("🧠 Active Models: Gemma-2-2B-it (Standard) & Qwen2.5-1.5B (Bro)")
    print("Local UI: http://localhost:3000")
    print("Discovery: Companion devices will auto-discover this Mac via /my-endpoint!")
    print("Press Ctrl+C to safely stop the pipeline.")
    print("=" * 60 + "\n")

    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        cleanup(None, None)

if __name__ == "__main__":
    main()
