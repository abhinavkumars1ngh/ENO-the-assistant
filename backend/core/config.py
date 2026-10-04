"""
Central runtime configuration for the ENO backend.

Everything environment-specific lives here so the same code runs:
  * locally on an Apple Silicon Mac (ENO_MODE=local, MLX inference, SQLite), and
  * on a Linux container host such as Render / Railway / Fly (ENO_MODE=cloud,
    hosted inference endpoint, Postgres).

A plain `KEY=value` file at the project root named `.env` is loaded if present
(real environment variables always win).
"""
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(PROJECT_ROOT / ".env")


def _bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _csv(name: str, default: str) -> list[str]:
    return [p.strip() for p in os.getenv(name, default).split(",") if p.strip()]


# --- Mode ---------------------------------------------------------------
ENO_MODE = os.getenv("ENO_MODE", "local").strip().lower()
IS_CLOUD = ENO_MODE == "cloud"

# --- Storage ------------------------------------------------------------
STORAGE_DIR = Path(os.getenv("STORAGE_DIR") or PROJECT_ROOT / "storage")


def _normalize_db_url(url: str) -> str:
    # Heroku/Render/Supabase sometimes hand out the legacy "postgres://" scheme.
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


DATABASE_URL = _normalize_db_url(
    os.getenv("DATABASE_URL") or f"sqlite:///{STORAGE_DIR}/db/eno.db"
)

# --- Auth ---------------------------------------------------------------
_LEGACY_LOCAL_JWT_SECRET = "super-secret-eno-key-change-in-production"
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    if IS_CLOUD:
        raise RuntimeError("JWT_SECRET must be set when ENO_MODE=cloud")
    # Local dev only: keeps previously issued local tokens valid.
    JWT_SECRET = _LEGACY_LOCAL_JWT_SECRET
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

# Audience the backend accepts when verifying Google ID tokens (same OAuth client
# ID the frontend's NextAuth uses).
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

CORS_ORIGINS = _csv("CORS_ORIGINS", "*")

# --- Inference ----------------------------------------------------------
# "mlx"    -> local Apple MLX weights (needs Apple Silicon)
# "openai" -> any OpenAI-compatible /chat/completions endpoint (Groq, Together,
#             OpenRouter, vLLM, llama.cpp server, a serverless GPU endpoint ...)
LLM_BACKEND = (os.getenv("LLM_BACKEND") or ("openai" if IS_CLOUD else "mlx")).lower()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL_STANDARD = os.getenv("LLM_MODEL_STANDARD", "")
LLM_MODEL_BRO = os.getenv("LLM_MODEL_BRO", "") or LLM_MODEL_STANDARD
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))

# Optional hosted speech-to-text (OpenAI-compatible /audio/transcriptions).
# Empty -> falls back to local mlx_whisper (local mode only).
STT_MODEL = os.getenv("STT_MODEL", "")

# --- Features that need the full local stack ---------------------------
# Qdrant / Celery / sentence-transformers / Apple Vision OCR / device MCP are not
# part of the lightweight cloud image.
LOCAL_STACK_ENABLED = not IS_CLOUD
URL_AUGMENT_ENABLED = _bool("ENO_ENABLE_URL_AUGMENT", default=not IS_CLOUD)

# --- Payments (Razorpay) -----------------------------------------------
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_eno_sandbox")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "eno_sandbox_secret_key_123")
RAZORPAY_TEST_MODE = RAZORPAY_KEY_ID.startswith("rzp_test_")
