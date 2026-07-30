import socket
from celery import Celery

def is_redis_running(host="127.0.0.1", port=6379, timeout=0.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

# Dynamically choose Celery broker/backend
if is_redis_running():
    print("[Eno AI] Redis detected on port 6379. Connecting Celery to Docker/Redis.")
    BROKER_URL = "redis://127.0.0.1:6379/0"
    BACKEND_URL = "redis://127.0.0.1:6379/0"
    EAGER_MODE = False
else:
    print("[Eno AI] Redis not found on port 6379. Falling back to Eager (in-memory) execution.")
    BROKER_URL = "memory://"
    BACKEND_URL = "cache+memory://"
    EAGER_MODE = True

celery_app = Celery(
    "eno_worker",
    broker=BROKER_URL,
    backend=BACKEND_URL
)

celery_app.conf.update(
    task_always_eager=EAGER_MODE,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
)
