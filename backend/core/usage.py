"""
Usage metering + plan enforcement.

Privacy contract: this module only ever stores *metadata* (user, time, model, output size,
duration). Message bodies are never passed in here and never written anywhere on the server.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.core.plans import PLANS, PLAN_ORDER, effective_plan, plan_rank
from backend.models.schema import UsageEvent, User


def _start_of_utc_day() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def messages_today(db: Session, user_id: int) -> int:
    return (
        db.query(func.count(UsageEvent.id))
        .filter(
            UsageEvent.user_id == user_id,
            UsageEvent.kind == "chat",
            UsageEvent.created_at >= _start_of_utc_day(),
        )
        .scalar()
        or 0
    )


def record_usage(
    db: Session,
    user_id: int,
    kind: str = "chat",
    model: Optional[str] = None,
    output_chars: int = 0,
    duration_ms: int = 0,
) -> None:
    db.add(
        UsageEvent(
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            kind=kind,
            model=model,
            output_chars=output_chars,
            duration_ms=duration_ms,
        )
    )
    db.commit()


def min_plan_for_model(model: str) -> str:
    for pid in PLAN_ORDER:
        if model in PLANS[pid]["models"]:
            return pid
    return PLAN_ORDER[-1]


def check_chat_allowed(db: Session, user: User, model: str) -> Optional[dict]:
    """
    Returns None if the request may proceed, otherwise a frame the client can render as an
    upgrade prompt: {"type": "error", "code": "upgrade_required" | "limit_reached", ...}
    """
    plan = effective_plan(user)
    cfg = PLANS[plan]

    if model not in cfg["models"]:
        needed = min_plan_for_model(model)
        return {
            "type": "error",
            "code": "upgrade_required",
            "required_plan": needed,
            "message": f"The '{model}' model is available on the {PLANS[needed]['label']} plan and above.",
        }

    limit = cfg["daily_messages"]
    if limit is not None:
        used = messages_today(db, user.id)
        if used >= limit:
            next_plan = PLAN_ORDER[min(plan_rank(plan) + 1, len(PLAN_ORDER) - 1)]
            return {
                "type": "error",
                "code": "limit_reached",
                "required_plan": next_plan,
                "message": f"You've used all {limit} messages for today on the {cfg['label']} plan.",
            }
    return None


def account_snapshot(db: Session, user: User) -> dict:
    plan = effective_plan(user)
    cfg = PLANS[plan]
    return {
        "plan": plan,
        "plan_label": cfg["label"],
        "daily_limit": cfg["daily_messages"],
        "used_today": messages_today(db, user.id),
        "models": cfg["models"],
        "voice": cfg["voice"],
    }
