from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.conversation import conversation_engine

router = APIRouter()


@router.websocket("/ws/chat/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str):
    """
    WebSocket endpoint for real-time text streaming.
    Audio is handled separately via POST /api/transcribe — once transcribed,
    the text is sent through this channel as a normal 'text' message.
    """
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
