import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.core.auth import get_current_user, verify_instance_owner
from backend.core.conversation import conversation_engine
from backend.core.database import SessionLocal
from backend.core.usage import check_chat_allowed, record_usage
from backend.models.schema import User

router = APIRouter()

VALID_MODELS = {"standard", "bro"}


@router.websocket("/ws/chat/{chat_id}")
async def websocket_endpoint(websocket: WebSocket, chat_id: str, token: str = None):
    """
    WebSocket endpoint for real-time text streaming.

    The server is stateless with respect to chat content: the browser sends the recent history
    with each message and keeps the transcript in its own on-device vault. `chat_id` is only an
    opaque label chosen by the client. We record usage METADATA (who / when / which model / how
    long), never message bodies.
    """
    if not token:
        await websocket.close(code=1008)
        return

    try:
        user = await get_current_user(token)
        # Always enforce strict single-owner pinning on the inference websocket
        verify_instance_owner(user, force_enforce=True)
    except Exception:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") != "text":
                continue

            query = (data.get("content") or "").strip()
            model_type = data.get("model", "standard")
            if model_type not in VALID_MODELS:
                model_type = "standard"

            if not query:
                continue

            # --- Plan enforcement (server-side, so the UI can't be bypassed) ---
            # Re-read the account each turn so an upgrade made mid-session applies immediately.
            db = SessionLocal()
            try:
                fresh_user = db.query(User).filter(User.id == user.id).first()
                if fresh_user is None:
                    await websocket.close(code=1008)
                    return
                blocked = check_chat_allowed(db, fresh_user, model_type)
            finally:
                db.close()
            if blocked:
                await websocket.send_json(blocked)
                await websocket.send_json({"type": "done"})
                continue

            started = time.monotonic()
            out_chars = 0
            async for chunk in conversation_engine.stream_response(
                query, history=data.get("history"), model_type=model_type, chat_id=chat_id
            ):
                if chunk.get("type") == "token":
                    out_chars += len(chunk.get("content", ""))
                await websocket.send_json(chunk)

            await websocket.send_json({"type": "done"})

            db = SessionLocal()
            try:
                record_usage(
                    db,
                    user.id,
                    kind="chat",
                    model=model_type,
                    output_chars=out_chars,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            finally:
                db.close()

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        # Log the error class only; exception text can echo request content.
        print(f"WebSocket error: {type(e).__name__}")
