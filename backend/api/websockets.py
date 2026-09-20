from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.conversation import conversation_engine

router = APIRouter()


from backend.core.auth import get_current_user
from backend.core.database import SessionLocal
from backend.models.schema import Conversation

@router.websocket("/ws/chat/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str, token: str = None):
    """
    WebSocket endpoint for real-time text streaming.
    """
    if not token:
        await websocket.close(code=1008)
        return
        
    try:
        user = await get_current_user(token)
    except Exception:
        await websocket.close(code=1008)
        return
        
    db = SessionLocal()
    chat = db.query(Conversation).filter(Conversation.id == chat_id, Conversation.user_id == user.id).first()
    db.close()
    
    if not chat:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "text":
                query = data.get("content", "").strip()
                model_type = data.get("model", "standard")
                
                if not query:
                    continue

                async for chunk in conversation_engine.stream_response(chat_id, query, model_type=model_type):
                    await websocket.send_json(chunk)

                await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        print(f"Client {chat_id} disconnected")
    except Exception as e:
        print(f"WebSocket error for chat {chat_id}: {e}")
