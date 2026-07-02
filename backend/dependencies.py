import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import decode_token
from database import get_session

# Vendored from mirage-bank/backend/dependencies.py — same rules
# (disabled/frozen rejection, role check) so a suspended bank user
# can't play casino games either.
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials

    try:
        user_id = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with get_session() as session:
        result = session.run(
            "MATCH (u:User {id: $user_id}) RETURN u",
            user_id=user_id,
        ).single()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = dict(result["u"])

    if user["status"] == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled",
        )
    if user["status"] == "frozen":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is frozen",
        )

    return user


def get_current_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user


def get_ws_user(token: str | None) -> dict | None:
    """Same validation as get_current_user, adapted for WebSocket handshakes
    (FastAPI's Depends(HTTPBearer) doesn't apply there). Returns None instead
    of raising — the WS route decides whether an anonymous/invalid token
    means "reject" or "allow as spectator"."""
    if not token:
        return None

    try:
        user_id = decode_token(token)
    except jwt.PyJWTError:
        return None

    with get_session() as session:
        result = session.run(
            "MATCH (u:User {id: $user_id}) RETURN u",
            user_id=user_id,
        ).single()

    if result is None:
        return None

    user = dict(result["u"])
    if user["status"] in ("disabled", "frozen"):
        return None

    return user
