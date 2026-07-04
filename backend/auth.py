from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from config import settings

# Vendored from mirage-bank/backend/auth.py — must stay byte-for-byte
# compatible (same claims, same algorithm) so tokens issued by either
# app are accepted by the other.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Passwords ────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password too long (bcrypt limit is 72 bytes)")
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    # bcrypt silently truncates at 72 bytes; reject over-length input here so
    # a >72-byte password can't be "verified" by matching a truncated prefix.
    if len(plain.encode("utf-8")) > 72:
        return False
    return pwd_context.verify(plain, hashed)


# ── JWT tokens ───────────────────────────────────────────────────
def create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> str:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    user_id: str = payload.get("sub")
    if user_id is None:
        raise jwt.InvalidTokenError("Missing subject")
    return user_id
