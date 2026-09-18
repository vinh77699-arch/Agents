"""JWT and password utilities using only Python built-ins."""
import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import settings

_SECRET = settings.jwt_secret.encode()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"{salt}:{h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, h_hex = stored.split(":", 1)
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
        return hmac.compare_digest(h.hex(), h_hex)
    except Exception:
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (pad % 4))


def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": int(time.time()) + settings.jwt_expire_hours * 3600,
    }
    header = _b64(b'{"alg":"HS256","typ":"JWT"}')
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64(hmac.new(_SECRET, f"{header}.{body}".encode(), hashlib.sha256).digest())
    return f"{header}.{body}.{sig}"


def decode_token(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, body, sig = parts
        expected = _b64(hmac.new(_SECRET, f"{header}.{body}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_unb64(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None
