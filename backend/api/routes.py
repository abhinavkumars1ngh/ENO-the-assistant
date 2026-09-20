from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.auth import get_current_user, create_access_token
from passlib.context import CryptContext
from backend.models.schema import Conversation, Message, Memory, User
from backend.services.ingestion import process_pdf_task, process_video_task, process_image_task
from backend.services.voice_service import voice_service
from pydantic import BaseModel
import shutil
import os
import uuid
import datetime
import tempfile
import subprocess
import bcrypt

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class GoogleAuthSync(BaseModel):
    email: str

@router.post("/login")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Incorrect username or password")
        
    try:
        # Check password
        if not bcrypt.checkpw(form_data.password.encode('utf-8'), user.hashed_password.encode('utf-8')):
            raise HTTPException(status_code=401, detail="Incorrect username or password")
    except Exception:
        # Fallback if the hash isn't pure bcrypt format
        if not pwd_context.verify(form_data.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Incorrect username or password")
            
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id, "role": user.role}

@router.post("/auth/sync")
def sync_oauth_user(data: GoogleAuthSync, db: Session = Depends(get_db)):
    """Syncs a Google OAuth user from NextAuth to the FastAPI database and returns a JWT."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        user = User(email=data.email, role="user")
        db.add(user)
        db.commit()
        db.refresh(user)
        
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer", "user_id": user.id, "role": user.role}


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


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    Accepts an audio file upload (webm/wav), transcribes it with Whisper,
    and returns the text. This is the reliable alternative to WebSocket audio.
    """
    temp_webm = None
    temp_wav = None
    try:
        # Write the uploaded audio to a temp file
        suffix = ".webm" if "webm" in (file.content_type or "") else ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            content = await file.read()
            f.write(content)
            temp_webm = f.name

        # Convert to wav if needed
        if suffix == ".webm":
            temp_wav = _convert_webm_to_wav(temp_webm)
        else:
            temp_wav = temp_webm

        # Transcribe
        text = voice_service.transcribe_audio(temp_wav)

        if not text or not text.strip():
            return {"text": "", "error": "Could not detect speech. Please try again."}

        return {"text": text.strip()}

    except Exception as e:
        print(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for f in [temp_webm, temp_wav]:
            if f and os.path.exists(f):
                try:
                    os.unlink(f)
                except OSError:
                    pass


@router.post("/ingest/pdf")
async def upload_pdf(course: str = Form(...), title: str = Form(...), file: UploadFile = File(...)):
    # Save file temporarily
    file_path = f"/Users/abhinavkumarsingh/ENO/storage/documents/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Trigger celery background task
    process_pdf_task.delay(file_path, course, title)
    
    return {"message": "PDF ingestion started", "filename": file.filename}

@router.post("/ingest/chat_file")
async def upload_chat_file(chat_id: str = Form(...), file: UploadFile = File(...)):
    file_path = f"/Users/abhinavkumarsingh/ENO/storage/documents/{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
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
async def ingest_video(course: str = Form(...), video_url: str = Form(...)):
    process_video_task.delay(video_url, course)
    return {"message": "Video ingestion started", "url": video_url}

# --- Chat Management Endpoints ---

@router.get("/chats")
def get_chats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetch all conversations for the logged in user, ordered by most recently updated."""
    chats = db.query(Conversation).filter(Conversation.user_id == current_user.id).order_by(Conversation.updated.desc()).all()
    return {"chats": [{"id": c.id, "title": c.title, "updated": c.updated} for c in chats]}

@router.post("/chats")
def create_chat(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new conversation."""
    chat_id = str(uuid.uuid4())
    new_chat = Conversation(
        id=chat_id,
        user_id=current_user.id,
        title="New Chat",
        created=datetime.datetime.utcnow(),
        updated=datetime.datetime.utcnow()
    )
    db.add(new_chat)
    db.commit()
    return {"id": chat_id, "title": "New Chat"}

@router.get("/chats/{chat_id}/messages")
def get_chat_messages(chat_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetch all messages for a specific conversation, ensuring ownership."""
    # Verify ownership
    chat = db.query(Conversation).filter(Conversation.id == chat_id, Conversation.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    messages = db.query(Message).filter(Message.conversation_id == chat_id).order_by(Message.timestamp.asc()).all()
    return {"messages": [{"role": m.role, "content": m.content, "timestamp": m.timestamp} for m in messages]}

@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a conversation and its messages."""
    chat = db.query(Conversation).filter(Conversation.id == chat_id, Conversation.user_id == current_user.id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
        
    db.query(Message).filter(Message.conversation_id == chat_id).delete()
    db.delete(chat)
    db.commit()
    return {"status": "ok"}

# --- Memory Endpoints ---

@router.get("/memory")
def get_persona_memory(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetch the synthesized user persona/style preferences."""
    memories = db.query(Memory).filter(Memory.user_id == current_user.id, Memory.type == "persona").order_by(Memory.timestamp.desc()).all()
    return {"persona": [m.fact for m in memories]}
