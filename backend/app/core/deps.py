"""FastAPI dependency helpers."""
from typing import Optional

from fastapi import Depends, Header, HTTPException

from app.core import database as db
from app.core.security import decode_token


async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Return user dict if valid Bearer token, else None (guest)."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    if not payload:
        return None
    user = await db.get_user_by_id(payload["sub"])
    if not user or not user.get("is_active"):
        return None
    return user


async def require_user(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if user is None:
        raise HTTPException(status_code=401, detail="Yêu cầu đăng nhập")
    return user


async def require_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Cần quyền quản trị viên")
    return user
