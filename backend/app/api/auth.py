"""Authentication: register, login, me, admin user list."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core import database as db
from app.core.config import settings
from app.core.deps import get_current_user, require_admin, require_user
from app.core.security import create_token, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter()


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5)
    password: str = Field(..., min_length=6)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/auth/register", response_model=TokenResponse, tags=["auth"])
async def register(req: RegisterRequest):
    existing = await db.get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email đã được đăng ký")

    now = datetime.now(timezone.utc).isoformat()
    user_id = str(uuid.uuid4())
    # First user gets admin role
    all_sessions = await db.list_sessions(limit=1)
    existing_users = await db.get_user_by_email(settings.admin_email)
    role = "admin" if req.email == settings.admin_email else "user"

    pw_hash = hash_password(req.password)
    ok = await db.create_user(user_id, req.email, pw_hash, role, now)
    if not ok:
        raise HTTPException(status_code=409, detail="Email đã được đăng ký")

    user = await db.get_user_by_id(user_id)
    token = create_token(user_id, req.email, role)
    logger.info(f"[Auth] Registered {req.email} ({role})")
    return TokenResponse(
        access_token=token,
        user={"id": user_id, "email": req.email, "role": role, "daily_quota": user["daily_quota"]},
    )


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
async def login(req: LoginRequest):
    user = await db.get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email hoặc mật khẩu không đúng")
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Tài khoản đã bị khoá")

    token = create_token(user["id"], user["email"], user["role"])
    logger.info(f"[Auth] Login {req.email}")
    return TokenResponse(
        access_token=token,
        user={"id": user["id"], "email": user["email"], "role": user["role"],
              "daily_quota": user["daily_quota"], "reports_today": user["reports_today"]},
    )


@router.get("/auth/me", tags=["auth"])
async def me(current_user: dict = Depends(require_user)):
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "role": current_user["role"],
        "daily_quota": current_user["daily_quota"],
        "reports_today": current_user["reports_today"],
    }


@router.get("/admin/users", tags=["admin"])
async def list_users(admin: dict = Depends(require_admin)):
    """Admin: list all users."""
    conn_fn = db._get_user_by_email_sync  # noqa
    import asyncio, functools
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, _list_all_users)
    return rows


def _list_all_users():
    import sqlite3
    from app.core.config import settings as s
    conn = sqlite3.connect(s.sqlite_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, email, role, daily_quota, reports_today, is_active, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.patch("/admin/users/{user_id}/lock", tags=["admin"])
async def toggle_lock(user_id: str, lock: bool = True, admin: dict = Depends(require_admin)):
    import asyncio, functools
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, functools.partial(_set_active, user_id, not lock))
    return {"user_id": user_id, "is_active": not lock}


def _set_active(user_id: str, active: bool):
    import sqlite3
    from app.core.config import settings as s
    conn = sqlite3.connect(s.sqlite_path)
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (int(active), user_id))
    conn.commit()
    conn.close()
