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
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core import config
from backend.core.auth import get_current_user, get_db
from backend.core.plans import CURRENCY, PLANS, effective_plan, plan_rank, public_plans
from backend.core.usage import account_snapshot
from backend.models.schema import Payment, User

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
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Could not reach Razorpay")
    if resp.status_code != 200:
        print(f"Razorpay order creation failed: HTTP {resp.status_code}")
        raise HTTPException(status_code=502, detail="Razorpay rejected the order")

    order = resp.json()
    db.add(
        Payment(
            user_id=user.id,
            plan=body.plan,
            amount_paise=amount,
            currency=CURRENCY,
            razorpay_order_id=order["id"],
            status="created",
        )
    )
    db.commit()
    return {
        "order_id": order["id"],
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
    if not hmac.compare_digest(expected, body.razorpay_signature):
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
