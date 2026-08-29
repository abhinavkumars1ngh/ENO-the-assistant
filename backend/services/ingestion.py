from backend.core.celery_app import celery_app
from backend.services.embedding_service import embedding_service
from backend.core.qdrant_setup import client as qdrant_client
from qdrant_client.models import PointStruct
import fitz # PyMuPDF
import uuid
import os

@celery_app.task
def process_pdf_task(file_path: str, course: str, title: str, chat_id: str = None):
    print(f"Processing PDF: {file_path}")
    doc = fitz.open(file_path)
    
    chunks = []
    # Very basic chunking logic for prototype
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        
        # Simple splitting by double newline to simulate paragraph chunking
        paragraphs = text.split('\n\n')
        for i, para in enumerate(paragraphs):
            if len(para.strip()) > 50: # Ignore very small chunks
                chunks.append({
                    "text": para.strip(),
                    "page": page_num + 1,
                    "chunk_number": i
                })

    # Embed and Store
    for chunk in chunks:
        vector = embedding_service.embed_text(chunk["text"])
        point_id = str(uuid.uuid4())
        
        payload = {
            "text": chunk["text"],
            "course": course,
            "title": title,
            "page": chunk["page"],
            "source_type": "chat_pdf" if chat_id else "pdf"
        }
        if chat_id:
            payload["chat_id"] = chat_id
            
        qdrant_client.upsert(
            collection_name="knowledge_base",
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )
    print(f"Finished processing PDF: {file_path}")

@celery_app.task
def process_image_task(file_path: str, chat_id: str = None):
    print(f"Processing Image OCR: {file_path}")
    from ocrmac import ocrmac
    
    try:
        annotations = ocrmac.OCR(file_path).recognize()
        text = " ".join([ann[0] for ann in annotations])
        
        if not text.strip():
            print(f"No text found in image {file_path}")
            return ""
            
        vector = embedding_service.embed_text(text)
        point_id = str(uuid.uuid4())
        
        payload = {
            "text": f"[Image OCR Content]\n{text}",
            "course": "Chat Context",
            "title": os.path.basename(file_path),
            "page": 1,
            "source_type": "chat_image" if chat_id else "image"
        }
        if chat_id:
            payload["chat_id"] = chat_id
            
        qdrant_client.upsert(
            collection_name="knowledge_base",
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )
        print(f"Finished OCR processing: {file_path}")
        return text
    except Exception as e:
        print(f"OCR Error on {file_path}: {e}")
        return ""

@celery_app.task
def process_video_task(video_url: str, course: str):
    # Simulated video ingestion pipeline
    print(f"Downloading & Transcribing Video: {video_url}")
    # 1. yt-dlp to download audio
    # 2. whisper to transcribe
    # 3. chunk transcription by timestamps
    # 4. embed and store in Qdrant
    print("Video ingestion simulation complete.")
