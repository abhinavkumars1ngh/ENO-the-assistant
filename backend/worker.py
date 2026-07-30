from backend.core.celery_app import celery_app
from backend.services.ingestion import process_pdf_task, process_video_task

# Import tasks so Celery worker can register them
__all__ = ["celery_app", "process_pdf_task", "process_video_task"]
