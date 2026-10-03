"""
End-to-end backend tests for the cloud demo: stateless chat, plan gating, usage metering and
Razorpay test-mode verification. Runs on plain Linux with only requirements-cloud.txt installed
(no MLX / Qdrant / Celery), which doubles as a check that the container image boots.

    pip install -r requirements-cloud.txt pytest
    python -m pytest backend/tests -q
"""
import hashlib
import hmac
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.update(
    {
        "ENO_MODE": "cloud",
        "JWT_SECRET": "test-secret",
        "DATABASE_URL": f"sqlite:///{_tmp}/test.db",
        "STORAGE_DIR": _tmp,
        "GOOGLE_CLIENT_ID": "test-client-id",
        "RAZORPAY_KEY_ID": "rzp_test_abc",
        "RAZORPAY_KEY_SECRET": "shhh",
        "LLM_BASE_URL": "http://llm.invalid/v1",
        "LLM_MODEL_STANDARD": "std-model",
        "LLM_MODEL_BRO": "bro-model",
    }
)

import pytest
from fastapi.testclient import TestClient

from backend.core.auth import default_token_for
from backend.core.database import SessionLocal
from backend.main import app
from backend.models.schema import Message, Payment, UsageEvent, User
from backend.services.llm_service import llm_service


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:  # runs startup -> init_db()
        yield c


def make_user(email: str, **kw) -> tuple[User, dict]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, role="user", plan="free", **kw)
            db.add(user)
            db.commit()
            db.refresh(user)
        token = default_token_for(user)
        return user, {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


@pytest.fixture
def fake_llm(monkeypatch):
    seen = {}

    async def fake_stream(prompt=None, max_tokens=512, temp=0.7, model_type="standard", messages=None):
        seen["messages"] = messages
        seen["model_type"] = model_type
        for piece in ["Hello", " there"]:
            yield piece

    monkeypatch.setattr(llm_service, "stream_generate", fake_stream)
    return seen


def test_boots_and_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_google_sync_rejects_forged_credentials(client):
    r = client.post("/api/auth/sync", json={"id_token": "not-a-real-token"})
    assert r.status_code == 401
    # The old, unauthenticated shape ({"email": ...}) must no longer mint sessions.
    r = client.post("/api/auth/sync", json={"email": "victim@example.com"})
    assert r.status_code == 422


def test_protected_routes_need_auth(client):
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/ingest/pdf", data={"course": "x", "title": "y"}).status_code in (401, 422)
    assert client.post("/api/billing/order", json={"plan": "plus"}).status_code == 401


def test_me_returns_plan_and_opaque_uid(client):
    user, headers = make_user("me@example.com")
    body = client.get("/api/me", headers=headers).json()
    assert body["plan"] == "free"
    assert body["daily_limit"] == 20
    assert len(body["uid"]) == 32 and body["uid"] != str(user.id)


def test_chat_is_stateless_and_uses_client_history(client, fake_llm):
    user, headers = make_user("chat@example.com")
    token = headers["Authorization"].split()[1]
    history = [
        {"role": "user", "content": "my name is Zed"},
        {"role": "assistant", "content": "nice to meet you Zed"},
    ]
    with client.websocket_connect(f"/ws/chat/some-client-chat-id?token={token}") as ws:
        ws.send_json({"type": "text", "content": "what is my name?", "model": "standard", "history": history})
        frames = []
        while True:
            f = ws.receive_json()
            frames.append(f)
            if f["type"] == "done":
                break

    assert "".join(f["content"] for f in frames if f["type"] == "token") == "Hello there"
    msgs = fake_llm["messages"]
    assert msgs[0]["role"] == "system"
    assert [m["content"] for m in msgs[1:]][:2] == ["my name is Zed", "nice to meet you Zed"]
    assert msgs[-1]["role"] == "user" and "what is my name?" in msgs[-1]["content"]

    db = SessionLocal()
    try:
        # Privacy contract: no chat bodies stored; only a usage metadata row.
        assert db.query(Message).count() == 0
        events = db.query(UsageEvent).filter(UsageEvent.user_id == user.id).all()
        assert len(events) == 1 and events[0].model == "standard" and events[0].output_chars == len("Hello there")
        assert not any(hasattr(UsageEvent, c) for c in ("content", "body", "text", "prompt"))
    finally:
        db.close()


def test_bro_model_is_gated_for_free_users(client, fake_llm):
    _, headers = make_user("gated@example.com")
    token = headers["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/chat/x?token={token}") as ws:
        ws.send_json({"type": "text", "content": "hi", "model": "bro"})
        first = ws.receive_json()
        assert first["type"] == "error" and first["code"] == "upgrade_required"
        assert first["required_plan"] == "plus"
        assert ws.receive_json()["type"] == "done"
    assert "messages" not in fake_llm  # the model was never called


def test_daily_limit_enforced(client, fake_llm):
    user, headers = make_user("limit@example.com")
    db = SessionLocal()
    try:
        for _ in range(20):
            db.add(UsageEvent(user_id=user.id, kind="chat", model="standard"))
        db.commit()
    finally:
        db.close()
    token = headers["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/chat/x?token={token}") as ws:
        ws.send_json({"type": "text", "content": "one more", "model": "standard"})
        assert ws.receive_json()["code"] == "limit_reached"


def test_voice_is_plus_only(client):
    _, headers = make_user("voice@example.com")
    r = client.post("/api/transcribe", headers=headers, files={"file": ("a.webm", b"x", "audio/webm")})
    assert r.status_code == 402


def test_razorpay_flow_upgrades_plan(client, fake_llm, monkeypatch):
    import backend.api.account as account

    class FakeResp:
        status_code = 200

        def json(self):
            return {"id": "order_TEST123"}

    captured = {}

    def fake_post(url, **kw):
        captured["json"] = kw["json"]
        return FakeResp()

    monkeypatch.setattr(account.httpx, "post", fake_post)

    user, headers = make_user("buyer@example.com")
    other, other_headers = make_user("other@example.com")

    order = client.post("/api/billing/order", headers=headers, json={"plan": "plus"}).json()
    assert order["order_id"] == "order_TEST123" and order["key_id"] == "rzp_test_abc"
    # Price is decided server-side.
    assert captured["json"]["amount"] == 49900

    payload = {
        "razorpay_order_id": "order_TEST123",
        "razorpay_payment_id": "pay_TEST456",
        "razorpay_signature": "deadbeef",
    }
    # Bad signature: rejected, plan unchanged.
    assert client.post("/api/billing/verify", headers=headers, json=payload).status_code == 400
    assert client.get("/api/me", headers=headers).json()["plan"] == "free"

    good = hmac.new(b"shhh", b"order_TEST123|pay_TEST456", hashlib.sha256).hexdigest()
    payload["razorpay_signature"] = good

    # Somebody else cannot redeem this order.
    assert client.post("/api/billing/verify", headers=other_headers, json=payload).status_code == 404

    ok = client.post("/api/billing/verify", headers=headers, json=payload)
    assert ok.status_code == 200 and ok.json()["plan"] == "plus"
    assert client.get("/api/me", headers=headers).json()["plan"] == "plus"

    # Idempotent re-verification, and the other account is untouched.
    assert client.post("/api/billing/verify", headers=headers, json=payload).status_code == 200
    assert client.get("/api/me", headers=other_headers).json()["plan"] == "free"

    # The upgrade is visible immediately: bro now works on the same account.
    token = headers["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/chat/x?token={token}") as ws:
        ws.send_json({"type": "text", "content": "hi", "model": "bro"})
        assert ws.receive_json()["type"] == "token"

    # Can't buy what you already have; test-mode reset puts the demo back to Free.
    assert client.post("/api/billing/order", headers=headers, json={"plan": "plus"}).status_code == 400
    assert client.post("/api/billing/reset", headers=headers).json()["plan"] == "free"

    db = SessionLocal()
    try:
        assert db.query(Payment).filter(Payment.razorpay_order_id == "order_TEST123").one().status == "paid"
    finally:
        db.close()
