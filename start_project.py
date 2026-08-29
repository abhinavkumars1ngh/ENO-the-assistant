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
                p.terminate()
            except Exception:
                pass
                
    # Force kill any orphaned processes (like Next.js node instances)
    subprocess.run(["pkill", "-f", "ngrok http"], capture_output=True)
    subprocess.run(["pkill", "-f", "caffeinate"], capture_output=True)
    try:
        kill_port(8000)
        kill_port(3000)
    except NameError:
        pass # In case kill_port isn't parsed yet
        
    print("[Eno AI] Cleanup complete. Mac will now be allowed to sleep. Exiting.")
    sys.exit(0)

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

def main():
    base_dir = "/Users/abhinavkumarsingh/ENO"

    print("[Eno AI] Cleaning up existing ports (8000, 3000) and legacy tunnels...")
    kill_port(8000)
    kill_port(3000)
    subprocess.run(["pkill", "-f", "ngrok http"], capture_output=True)
    subprocess.run(["pkill", "-f", "caffeinate"], capture_output=True)
    subprocess.run(["pkill", "-f", "uvicorn backend.main:app"], capture_output=True)

    lock_file = os.path.join(base_dir, "storage", "qdrant", ".lock")
    if os.path.exists(lock_file):
        os.remove(lock_file)
#WARNING
    python_bin = os.path.join(base_dir, "venv312", "bin", "python")
    autoeck_path = os.path.join(base_dir, "autoeck.py")

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

    print("[Eno AI] Starting backend API (FastAPI) and initializing Gemma & Qwen models in memory...")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    backend = subprocess.Popen(
        [python_bin, "-m", "uvicorn", "backend.main:app", "--port", "8000"],
        cwd=base_dir,
        env=env
    )
    processes.append(backend)

    time.sleep(2)

    print("[Eno AI] Starting frontend (Next.js)...")
    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=os.path.join(base_dir, "frontend")
    )
    processes.append(frontend)

    print("[Eno AI] Starting Ngrok Tunnel (cross-thing-sinless.ngrok-free.dev)...")
    ngrok = subprocess.Popen(
        ["ngrok", "http", "--domain=cross-thing-sinless.ngrok-free.dev", "8000"]
    )
    processes.append(ngrok)

    print("[Eno AI] Running Caffeinate to prevent Mac from sleeping...")
    caffeinate = subprocess.Popen(["caffeinate", "-d"])
    processes.append(caffeinate)

    print("\n" + "=" * 50)
    print("✅ Pipeline is running! Eno AI is online.")
    print("🧠 Active Models: Gemma 2 2B (Standard) & Qwen (Bro)")
    print("Local Frontend: http://localhost:3000")
    print("Remote Phone URL: https://frontend-two-topaz-41.vercel.app")
    print("Press Ctrl+C to safely stop the pipeline.")
    print("=" * 50 + "\n")

    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        cleanup(None, None)

if __name__ == "__main__":
    main()
