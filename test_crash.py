import asyncio
import sys
sys.path.append(".")
from backend.core.conversation import conversation_engine

async def main():
    chat_id = "test_chat"
    message = "https://www.youtube.com/watch?v=SEIE4RlAjiO please refer that video and tell me what is going on here"
    
    # ensure chat exists
    from backend.core.database import SessionLocal
    from backend.models.schema import Conversation
    db = SessionLocal()
    if not db.query(Conversation).filter(Conversation.id == chat_id).first():
        db.add(Conversation(id=chat_id, title="Test"))
        db.commit()
    db.close()
    
    print("Starting generation...")
    try:
        async for chunk in conversation_engine.stream_response(chat_id, message):
            print(chunk)
    except Exception as e:
        print("EXCEPTION CAUGHT:", repr(e))

asyncio.run(main())
