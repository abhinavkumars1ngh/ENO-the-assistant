from sqlalchemy.orm import Session
from backend.models.schema import Memory, Message
from backend.core.database import SessionLocal
from backend.services.llm_service import llm_service
import datetime
import asyncio
import json

class MemoryEngine:
    """
    Manages Working Memory, Session Memory, and Long-Term Memory (Persona).
    """
    def __init__(self):
        pass

    def add_memory(self, user_id: int, memory_type: str, fact: str, confidence: float = 1.0):
        db = SessionLocal()
        try:
            # Overwrite persona if it exists (we keep one unified persona summary for now)
            if memory_type == "persona":
                db.query(Memory).filter(Memory.user_id == user_id, Memory.type == "persona").delete()
            
            new_memory = Memory(
                user_id=user_id,
                type=memory_type,
                fact=fact,
                confidence=confidence,
                timestamp=datetime.datetime.utcnow()
            )
            db.add(new_memory)
            db.commit()
        finally:
            db.close()

    def get_memories(self, user_id: int, memory_type: str = None) -> list[str]:
        db = SessionLocal()
        try:
            query = db.query(Memory).filter(Memory.user_id == user_id)
            if memory_type:
                query = query.filter(Memory.type == memory_type)
            
            memories = query.order_by(Memory.timestamp.desc()).limit(20).all()
            return [m.fact for m in memories]
        finally:
            db.close()

    async def extract_persona_async(self, chat_id: str):
        """Asynchronously read chat history and update user persona preferences."""
        db = SessionLocal()
        try:
            # Fetch recent user messages
            messages = db.query(Message).filter(Message.conversation_id == chat_id, Message.role == "user").order_by(Message.timestamp.desc()).limit(15).all()
            if len(messages) < 3:
                return # Not enough data yet
                
            history_text = "\n".join([f"User: {m.content}" for m in reversed(messages)])
        finally:
            db.close()
            
        prompt = f"""<|im_start|>system
You are a profiling AI. Analyze the following user messages.
Extract a 2-3 sentence summary of the user's texting style, preferences, tone, and any key facts they mentioned.
Focus ONLY on how they communicate (e.g. casual, formal, slang, precise) and what they want.
Output nothing else but the summary.<|im_end|>
<|im_start|>user
{history_text}<|im_end|>
<|im_start|>assistant
"""
        
        persona_summary = ""
        async for chunk in llm_service.stream_generate(prompt, max_tokens=150, temp=0.2):
            persona_summary += chunk
            
        if persona_summary.strip():
            # Save the new persona profile (hardcoded user_id=1 for now)
            self.add_memory(1, "persona", persona_summary.strip())
            print(f"Updated Persona Memory: {persona_summary.strip()}")

memory_engine = MemoryEngine()
