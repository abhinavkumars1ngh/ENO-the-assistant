from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from backend.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    GOOGLE_CLIENT_ID,
    JWT_ALGORITHM,
    JWT_SECRET,
)
from backend.core.database import SessionLocal, get_db  # noqa: F401  (get_db re-exported for existing imports)
from backend.models import schema

# Kept as module-level names because other modules import them.
SECRET_KEY = JWT_SECRET
ALGORITHM = JWT_ALGORITHM

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def default_token_for(user: schema.User) -> str:
    return create_access_token(
        data={"sub": str(user.id), "email": getattr(user, "email", "")},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def verify_google_id_token(raw_id_token: str) -> dict:
    """
    Verify a Google-signed ID token (signature, expiry, issuer, audience) and
    return its claims. This is what stops anyone from minting a session for an
    arbitrary email address.
    """
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Server is missing GOOGLE_CLIENT_ID")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token as google_id_token

        claims = google_id_token.verify_oauth2_token(
            raw_id_token, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid Google credential")

    if not claims.get("email") or not claims.get("email_verified", False):
        raise HTTPException(status_code=401, detail="Google email is not verified")
    return claims


# In-memory tracking of the running instance owner
_instance_owner_id: Optional[int] = None
_instance_owner_email: Optional[str] = None


def get_instance_owner() -> dict:
    from backend.core.config import IS_CLOUD, LLM_BACKEND
    if IS_CLOUD and LLM_BACKEND != "mlx":
        return {"owner_id": None, "owner_email": None}
    return {
        "owner_id": _instance_owner_id,
        "owner_email": _instance_owner_email,
    }


def set_instance_owner(user_id: int, email: str = "", force_enforce: bool = False):
    from backend.core.config import IS_CLOUD, LLM_BACKEND
    is_inference_machine = (LLM_BACKEND == "mlx") or force_enforce
    if IS_CLOUD and not is_inference_machine:
        return
    global _instance_owner_id, _instance_owner_email
    if _instance_owner_id is None:
        _instance_owner_id = user_id
        _instance_owner_email = email
        print(f"[Eno Auth] Instance owner pinned to user_id={user_id} ({email})")


def verify_instance_owner(user: schema.User, force_enforce: bool = False):
    from backend.core.config import IS_CLOUD, LLM_BACKEND
    is_inference_machine = (LLM_BACKEND == "mlx") or force_enforce
    if IS_CLOUD and not is_inference_machine:
        return
    global _instance_owner_id
    if _instance_owner_id is None:
        set_instance_owner(user.id, getattr(user, "email", ""), force_enforce=force_enforce)
        return
    if _instance_owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: This ENO instance is locked to owner account ID {_instance_owner_id}. Access denied for user ID {user.id}.",
        )


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    db = SessionLocal()
    try:
        user = db.query(schema.User).filter(schema.User.id == int(user_id)).first()
        if user is None:
            raise credentials_exception

        # Enforce instance owner pinning on every authenticated request
        verify_instance_owner(user)
        return user
    finally:
        db.close()
