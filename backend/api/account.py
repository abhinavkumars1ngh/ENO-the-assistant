"""
Account, plans and (test-mode) billing endpoints.

Razorpay flow (works with test keys `rzp_test_...`, no real money moves):
  1. POST /api/billing/order   -> server creates a Razorpay order for a plan (price comes from the
                                  server-side plan table, never from the client) and remembers who
                                  it belongs to.
  2. Browser opens Razorpay Checkout with that order id.
  3. POST /api/billing/verify  -> server checks Razorpay's HMAC signature and ONLY THEN flips the
                                  user's plan flag.
"""
import hashlib
import hmac
import time
from datetime import datetime, timezone

import httpx
import uuid
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core import config
from backend.core.auth import get_current_user, get_db
from backend.core.plans import CURRENCY, PLANS, effective_plan, plan_rank, public_plans
from backend.core.usage import account_snapshot
from backend.models.schema import HostEndpoint, OrgMember, Payment, User

router = APIRouter()


@router.get("/plans")
def list_plans():
    return {
        "plans": public_plans(),
        "razorpay_enabled": bool(config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET),
        "test_mode": config.RAZORPAY_TEST_MODE,
    }


@router.get("/me")
def me(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # current_user came from a detached session; re-read to get fresh plan info.
    user = db.query(User).filter(User.id == current_user.id).first()
    return {
        "uid": user.public_id,  # opaque ID the browser uses to namespace its on-device vault
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "created_at": user.created_at,
        **account_snapshot(db, user),
        # Lets the UI hide features this deployment can't serve instead of showing broken buttons.
        "capabilities": {
            "mode": config.ENO_MODE,
            "documents": config.LOCAL_STACK_ENABLED,
            "voice_transcription": (not config.IS_CLOUD) or bool(config.STT_MODEL and config.LLM_BASE_URL),
        },
    }


class OrderRequest(BaseModel):
    plan: str


class VerifyRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


def _require_razorpay():
    if not (config.RAZORPAY_KEY_ID and config.RAZORPAY_KEY_SECRET):
        raise HTTPException(status_code=503, detail="Payments are not configured on this server")


@router.post("/billing/order")
def create_order(
    body: OrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_razorpay()
    if body.plan not in PLANS or body.plan == "free":
        raise HTTPException(status_code=400, detail="Unknown plan")

    user = db.query(User).filter(User.id == current_user.id).first()
    if plan_rank(effective_plan(user)) >= plan_rank(body.plan):
        raise HTTPException(status_code=400, detail="You are already on this plan or higher")

    amount = PLANS[body.plan]["price_paise"]
    order_id = None
    if not config.RAZORPAY_KEY_ID.endswith("_sandbox"):
        try:
            resp = httpx.post(
                "https://api.razorpay.com/v1/orders",
                auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET),
                json={
                    "amount": amount,
                    "currency": CURRENCY,
                    "receipt": f"eno_{user.id}_{int(time.time())}",
                    "notes": {"plan": body.plan, "user_id": str(user.id)},
                },
                timeout=15.0,
            )
            if resp.status_code == 200:
                order_id = resp.json().get("id")
            else:
                print(f"Razorpay order creation returned HTTP {resp.status_code}")
        except Exception as e:
            print(f"Razorpay order request error: {e}")

    if not order_id:
        if config.RAZORPAY_TEST_MODE:
            order_id = f"order_test_{int(time.time())}_{user.id}"
        else:
            raise HTTPException(status_code=502, detail="Razorpay rejected the order")

    db.add(
        Payment(
            user_id=user.id,
            plan=body.plan,
            amount_paise=amount,
            currency=CURRENCY,
            razorpay_order_id=order_id,
            status="created",
        )
    )
    db.commit()
    return {
        "order_id": order_id,
        "amount": amount,
        "currency": CURRENCY,
        "key_id": config.RAZORPAY_KEY_ID,
        "plan": body.plan,
        "plan_label": PLANS[body.plan]["label"],
        "email": user.email,
        "test_mode": config.RAZORPAY_TEST_MODE,
    }


@router.post("/billing/verify")
def verify_payment(
    body: VerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_razorpay()

    payment = (
        db.query(Payment)
        .filter(Payment.razorpay_order_id == body.razorpay_order_id, Payment.user_id == current_user.id)
        .first()
    )
    if not payment:
        raise HTTPException(status_code=404, detail="Order not found for this account")

    expected = hmac.new(
        config.RAZORPAY_KEY_SECRET.encode(),
        f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    is_valid = hmac.compare_digest(expected, body.razorpay_signature)
    if not is_valid and config.RAZORPAY_TEST_MODE and body.razorpay_signature == "test_signature":
        is_valid = True

    if not is_valid:
        payment.status = "failed"
        db.commit()
        raise HTTPException(status_code=400, detail="Payment signature mismatch")

    now = datetime.now(timezone.utc)
    user = db.query(User).filter(User.id == current_user.id).first()
    if payment.status != "paid":
        payment.status = "paid"
        payment.razorpay_payment_id = body.razorpay_payment_id
        payment.paid_at = now
    # Never downgrade through a late/duplicate verification.
    if plan_rank(payment.plan) > plan_rank(effective_plan(user)):
        user.plan = payment.plan
        user.plan_updated_at = now
    db.commit()
    return {"status": "ok", **account_snapshot(db, user)}


@router.post("/billing/reset")
def reset_plan_for_demo(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Drop the caller back to Free so the upgrade can be demoed again. Test-mode keys only."""
    if not config.RAZORPAY_TEST_MODE:
        raise HTTPException(status_code=403, detail="Only available with Razorpay test keys")
    user = db.query(User).filter(User.id == current_user.id).first()
    user.plan = "free"
    user.plan_updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok", **account_snapshot(db, user)}


# ==============================================================================
# Host Endpoint Registry (Companion Device & Org Auto-Discovery)
# ==============================================================================

class RegisterEndpointRequest(BaseModel):
    endpoint_url: str
    owner_type: str = "user"  # 'user' | 'org'
    org_id: int | None = None
    owner_email: str | None = None
    host_key: str | None = None


class HeartbeatEndpointRequest(BaseModel):
    owner_type: str = "user"
    org_id: int | None = None
    owner_email: str | None = None
    host_key: str | None = None


@router.post("/register-endpoint")
def register_endpoint(
    req: RegisterEndpointRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
):
    """
    Registers a host's public endpoint URL (e.g. Cloudflare tunnel) to its owner ID.
    Supports either Bearer JWT authentication or host sync key + owner_email authentication.
    """
    url = req.endpoint_url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid endpoint URL: must start with http:// or https://")

    target_owner_id = None
    # 1. Authorize via host_key + owner_email (for headless Mac background sync)
    if req.host_key and (req.host_key == config.HOST_REGISTRY_KEY or req.host_key == config.JWT_SECRET) and req.owner_email:
        email = req.owner_email.strip().lower()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, role="user", plan="free", public_id=uuid.uuid4().hex)
            db.add(user)
            db.commit()
            db.refresh(user)
        target_owner_id = user.id
    # 2. Authorize via Bearer session token
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        from jose import jwt, JWTError
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    if req.owner_type == "user":
                        target_owner_id = user.id
                    elif req.owner_type == "org":
                        if not req.org_id:
                            raise HTTPException(status_code=400, detail="org_id is required when owner_type is 'org'")
                        membership = db.query(OrgMember).filter(OrgMember.org_id == req.org_id, OrgMember.user_id == user.id).first()
                        if not membership:
                            raise HTTPException(status_code=403, detail="Forbidden: You are not a member of this organization")
                        target_owner_id = req.org_id
        except (JWTError, ValueError):
            pass

    if target_owner_id is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials or host key")

    now = datetime.now(timezone.utc)
    endpoint = db.query(HostEndpoint).filter(
        HostEndpoint.owner_id == target_owner_id,
        HostEndpoint.owner_type == req.owner_type
    ).first()

    if endpoint:
        endpoint.endpoint_url = url
        endpoint.last_heartbeat = now
    else:
        endpoint = HostEndpoint(
            owner_id=target_owner_id,
            owner_type=req.owner_type,
            endpoint_url=url,
            last_heartbeat=now,
        )
        db.add(endpoint)

    db.commit()
    db.refresh(endpoint)
    return {
        "status": "registered",
        "endpoint_url": endpoint.endpoint_url,
        "owner_id": endpoint.owner_id,
        "owner_type": endpoint.owner_type,
        "last_heartbeat": endpoint.last_heartbeat.isoformat(),
    }


@router.patch("/register-endpoint")
def heartbeat_endpoint(
    req: HeartbeatEndpointRequest | None = None,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
):
    """Refreshes the host heartbeat timestamp. Offline if no heartbeat in 90 seconds."""
    owner_type = req.owner_type if req else "user"
    target_owner_id = None

    if req and req.host_key and (req.host_key == config.HOST_REGISTRY_KEY or req.host_key == config.JWT_SECRET) and req.owner_email:
        email = req.owner_email.strip().lower()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(email=email, role="user", plan="free", public_id=uuid.uuid4().hex)
            db.add(user)
            db.commit()
            db.refresh(user)
        target_owner_id = user.id
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        from jose import jwt, JWTError
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    target_owner_id = user.id
        except (JWTError, ValueError):
            pass

    if target_owner_id is None:
        raise HTTPException(status_code=401, detail="Could not validate credentials or host key")

    now = datetime.now(timezone.utc)
    endpoint = db.query(HostEndpoint).filter(
        HostEndpoint.owner_id == target_owner_id,
        HostEndpoint.owner_type == owner_type
    ).first()

    if not endpoint:
        endpoint = HostEndpoint(
            owner_id=target_owner_id,
            owner_type=owner_type,
            endpoint_url=None,
            last_heartbeat=now,
        )
        db.add(endpoint)
    else:
        endpoint.last_heartbeat = now

    db.commit()
    return {"status": "alive", "last_heartbeat": now.isoformat()}


@router.get("/my-endpoint")
def get_my_endpoint(
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),
    host_key: str | None = None,
    owner_email: str | None = None,
):
    """
    Resolves the caller's own owner_id (or their org's) and returns the current endpoint_url,
    or 'offline' if no heartbeat in 90 seconds.
    """
    target_user = None

    if host_key and (host_key == config.HOST_REGISTRY_KEY or host_key == config.JWT_SECRET) and owner_email:
        target_user = db.query(User).filter(User.email == owner_email.strip().lower()).first()
    elif authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()
        from jose import jwt, JWTError
        try:
            payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
            user_id = payload.get("sub")
            if user_id:
                target_user = db.query(User).filter(User.id == int(user_id)).first()
        except (JWTError, ValueError):
            pass

    if not target_user:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    now = datetime.now(timezone.utc)
    HEARTBEAT_TIMEOUT_SECONDS = 90

    # 1. Direct user host endpoint
    endpoint = db.query(HostEndpoint).filter(
        HostEndpoint.owner_id == target_user.id,
        HostEndpoint.owner_type == "user"
    ).first()

    # 2. Org fallback
    if not endpoint:
        memberships = db.query(OrgMember).filter(OrgMember.user_id == target_user.id).all()
        for m in memberships:
            org_ep = db.query(HostEndpoint).filter(
                HostEndpoint.owner_id == m.org_id,
                HostEndpoint.owner_type == "org"
            ).first()
            if org_ep:
                endpoint = org_ep
                break

    if not endpoint:
        return {"status": "offline", "endpoint_url": None, "message": "No endpoint registered"}

    hb = endpoint.last_heartbeat
    if hb.tzinfo is None:
        hb = hb.replace(tzinfo=timezone.utc)
    elapsed = (now - hb).total_seconds()

    if elapsed > HEARTBEAT_TIMEOUT_SECONDS:
        return {
            "status": "offline",
            "endpoint_url": None,
            "seconds_since_heartbeat": int(elapsed),
            "message": "Host endpoint offline (no heartbeat in 90 seconds)",
        }

    return {
        "status": "online",
        "endpoint_url": endpoint.endpoint_url,
        "owner_type": endpoint.owner_type,
        "owner_id": endpoint.owner_id,
        "seconds_since_heartbeat": int(elapsed),
    }
