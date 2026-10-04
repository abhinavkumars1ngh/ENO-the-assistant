from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.core import config
from backend.core.database import get_db
from backend.core.auth import get_current_user, create_access_token, default_token_for, verify_google_id_token
from backend.core.plans import PLANS, effective_plan
from backend.core.usage import record_usage
from passlib.context import CryptContext
from backend.models.schema import Memory, User
from pydantic import BaseModel
import shutil
import os
import time
import datetime
import tempfile
import subprocess
import bcrypt

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class GoogleAuthSync(BaseModel):
    # Google-signed ID token from the NextAuth sign-in. The backend verifies it itself instead
    # of trusting a bare email address from the caller.
    id_token: str

def _session_payload(user: User) -> dict:
    return {
        "access_token": default_token_for(user),
        "token_type": "bearer",
        "user_id": user.id,
        "uid": user.public_id,
        "role": user.role,
        "plan": effective_plan(user),
    }

@router.post("/login")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    try:
        # Check password
        if not bcrypt.checkpw(form_data.password.encode('utf-8'), user.hashed_password.encode('utf-8')):
            raise HTTPException(status_code=401, detail="Incorrect username or password")
    except HTTPException:
        raise
    except Exception:
        # Fallback if the hash isn't pure bcrypt format
        if not pwd_context.verify(form_data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect username or password")

    return _session_payload(user)

@router.post("/auth/sync")
def sync_oauth_user(data: GoogleAuthSync, db: Session = Depends(get_db)):
    """Verifies a Google ID token, creates the account row on first sign-in, and returns a JWT."""
    from backend.core.auth import get_instance_owner, set_instance_owner

    claims = verify_google_id_token(data.id_token)
    email = claims["email"].lower()

    owner = get_instance_owner()
    if owner["owner_email"] and owner["owner_email"] != email:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: This running ENO instance is pinned to {owner['owner_email']}.",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, role="user", plan="free")
        db.add(user)
        db.commit()
        db.refresh(user)

    if owner["owner_id"] is None:
        set_instance_owner(user.id, email)

    # If start_project.py has captured a local Cloudflare tunnel URL, auto-register it to this user
    try:
        from backend.models.schema import HostEndpoint
        from datetime import datetime, timezone
        tunnel_file = config.STORAGE_DIR / "tunnel_url.txt"
        if tunnel_file.exists():
            t_url = tunnel_file.read_text().strip()
            if t_url.startswith("http"):
                now = datetime.now(timezone.utc)
                ep = db.query(HostEndpoint).filter(HostEndpoint.owner_id == user.id, HostEndpoint.owner_type == "user").first()
                if ep:
                    ep.endpoint_url = t_url
                    ep.last_heartbeat = now
                else:
                    ep = HostEndpoint(owner_id=user.id, owner_type="user", endpoint_url=t_url, last_heartbeat=now)
                    db.add(ep)
                db.commit()
                print(f"[Eno Registry] 🚀 Auto-registered tunnel {t_url} to authenticated owner {email}")
    except Exception as e:
        print(f"[Eno Registry] Notice: could not auto-link tunnel on login: {e}")

    return _session_payload(user)


def _convert_webm_to_wav(webm_path: str) -> str:
    """Convert webm audio to wav using ffmpeg for Whisper compatibility."""
    wav_path = webm_path.replace(".webm", ".wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", webm_path, "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
            capture_output=True, timeout=15
        )
        return wav_path
    except Exception as e:
        print(f"ffmpeg conversion failed: {e}")
        return webm_path


def _transcribe_hosted(audio_path: str, content_type: str) -> str:
    """Hosted Whisper via an OpenAI-compatible /audio/transcriptions endpoint (cloud mode)."""
    import httpx
    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}"} if config.LLM_API_KEY else {}
    with open(audio_path, "rb") as fh:
        resp = httpx.post(
            f"{config.LLM_BASE_URL}/audio/transcriptions",
            headers=headers,
            data={"model": config.STT_MODEL},
            files={"file": (os.path.basename(audio_path), fh, content_type or "audio/webm")},
            timeout=60.0,
        )
    if resp.status_code != 200:
        print(f"STT endpoint returned HTTP {resp.status_code}")
        return ""
    return resp.json().get("text", "")


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Accepts an audio file upload (webm/wav), transcribes it with Whisper,
    and returns the text. This is the reliable alternative to WebSocket audio.
    Voice is a Plus/Pro feature.
    """
    plan = effective_plan(current_user)
    if not PLANS[plan]["voice"]:
        raise HTTPException(status_code=402, detail="Voice chat is available on the Plus plan and above.")

    hosted = bool(config.STT_MODEL and config.LLM_BASE_URL)
    if config.IS_CLOUD and not hosted:
        raise HTTPException(status_code=503, detail="Voice transcription is not enabled on this server.")

    temp_webm = None
    temp_wav = None
    started = time.monotonic()
    try:
        # Write the uploaded audio to a temp file
        suffix = ".webm" if "webm" in (file.content_type or "") else ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            content = await file.read()
            f.write(content)
            temp_webm = f.name

        if hosted:
            temp_wav = temp_webm
            text = _transcribe_hosted(temp_webm, file.content_type)
        else:
            # Convert to wav if needed
            if suffix == ".webm":
                temp_wav = _convert_webm_to_wav(temp_webm)
            else:
                temp_wav = temp_webm

            # Transcribe
            from backend.services.voice_service import voice_service
            text = voice_service.transcribe_audio(temp_wav)

        record_usage(db, current_user.id, kind="transcribe", duration_ms=int((time.monotonic() - started) * 1000))

        if not text or not text.strip():
            return {"text": "", "error": "Could not detect speech. Please try again."}

        return {"text": text.strip()}

    except Exception as e:
        print(f"Transcription error: {type(e).__name__}")
        raise HTTPException(status_code=500, detail="Transcription failed")
    finally:
        for f in [temp_webm, temp_wav]:
            if f and os.path.exists(f):
                try:
                    os.unlink(f)
                except OSError:
                    pass


# --- Knowledge-base ingestion (local stack only: Qdrant + Celery + local embedding models) ---

def _require_local_stack():
    if not config.LOCAL_STACK_ENABLED:
        raise HTTPException(
            status_code=501,
            detail="Document upload needs the local ENO stack and is not part of the cloud demo.",
        )

def _save_upload(file: UploadFile) -> str:
    docs_dir = config.STORAGE_DIR / "documents"
    os.makedirs(docs_dir, exist_ok=True)
    # basename() blocks path traversal via crafted filenames
    file_path = str(docs_dir / os.path.basename(file.filename or "upload"))
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path

@router.post("/ingest/pdf")
async def upload_pdf(course: str = Form(...), title: str = Form(...), file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    _require_local_stack()
    from backend.services.ingestion import process_pdf_task
    file_path = _save_upload(file)

    # Trigger celery background task
    process_pdf_task.delay(file_path, course, title)

    return {"message": "PDF ingestion started", "filename": file.filename}

@router.post("/ingest/chat_file")
async def upload_chat_file(chat_id: str = Form(...), file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    _require_local_stack()
    from backend.services.ingestion import process_pdf_task, process_image_task
    file_path = _save_upload(file)

    ext = file.filename.lower().split('.')[-1]
    extracted_text = ""
    if ext in ['pdf']:
        process_pdf_task(file_path, "Chat Context", file.filename, chat_id=chat_id)
    elif ext in ['png', 'jpg', 'jpeg', 'webp', 'heic']:
        extracted_text = process_image_task(file_path, chat_id=chat_id)
    else:
        return {"error": "Unsupported file format"}

    return {"message": "Chat file ingestion started", "filename": file.filename, "extracted_text": extracted_text}

@router.post("/ingest/video")
async def ingest_video(course: str = Form(...), video_url: str = Form(...), current_user: User = Depends(get_current_user)):
    _require_local_stack()
    from backend.services.ingestion import process_video_task
    process_video_task.delay(video_url, course)
    return {"message": "Video ingestion started", "url": video_url}

# NOTE: The /chats endpoints were removed on purpose. Conversations are stored on the user's
# device (IndexedDB vault), not in a server-side chat table.

# --- Memory Endpoints ---

@router.get("/memory")
def get_persona_memory(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetch the synthesized user persona/style preferences."""
    memories = db.query(Memory).filter(Memory.user_id == current_user.id, Memory.type == "persona").order_by(Memory.timestamp.desc()).all()
    return {"persona": [m.fact for m in memories]}
