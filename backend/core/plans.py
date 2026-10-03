"""Plan / tier definitions. Prices are in paise (INR) because Razorpay works in the smallest currency unit."""

PLAN_ORDER = ["free", "plus", "pro"]

PLANS: dict[str, dict] = {
    "free": {
        "label": "Free",
        "price_paise": 0,
        "daily_messages": 20,
        "models": ["standard"],
        "voice": False,
        "tagline": "Try ENO",
    },
    "plus": {
        "label": "Plus",
        "price_paise": 49900,
        "daily_messages": 200,
        "models": ["standard", "bro"],
        "voice": True,
        "tagline": "Bigger model + voice",
    },
    "pro": {
        "label": "Pro",
        "price_paise": 99900,
        "daily_messages": None,  # unlimited
        "models": ["standard", "bro"],
        "voice": True,
        "tagline": "No daily limit",
    },
}

CURRENCY = "INR"


def plan_rank(plan: str) -> int:
    return PLAN_ORDER.index(plan) if plan in PLAN_ORDER else 0


def effective_plan(user) -> str:
    """Admins get everything; unknown values degrade to free."""
    if getattr(user, "role", None) == "admin":
        return "pro"
    plan = getattr(user, "plan", None) or "free"
    return plan if plan in PLANS else "free"


def public_plans() -> list[dict]:
    return [
        {
            "id": pid,
            "label": PLANS[pid]["label"],
            "price_paise": PLANS[pid]["price_paise"],
            "currency": CURRENCY,
            "daily_messages": PLANS[pid]["daily_messages"],
            "models": PLANS[pid]["models"],
            "voice": PLANS[pid]["voice"],
            "tagline": PLANS[pid]["tagline"],
        }
        for pid in PLAN_ORDER
    ]
