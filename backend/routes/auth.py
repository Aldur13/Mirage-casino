import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from auth import create_token, hash_password, verify_password
from database import get_session
from models import (
    LoginRequest, LoginResponse,
    RegisterRequest, RegisterResponse, UserResponse,
)

router = APIRouter()

# Mirrors mirage-bank/backend/routes/auth.py::register exactly (personal
# accounts only — youth/business signup stays a bank-only flow). Must be
# kept in sync: a user created here has to be indistinguishable from one
# created on the bank, since both apps read the same User/Account nodes.


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest):
    email = body.email.lower()

    with get_session() as session:
        existing = session.run(
            "MATCH (u:User {email: $email}) RETURN u.id", email=email
        ).single()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists",
            )

    user_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    password_hash = hash_password(body.password)

    with get_session() as session:
        session.run(
            """
            CREATE (u:User {
                id: $user_id, name: $name, email: $email,
                password_hash: $password_hash, role: 'user',
                status: 'active', account_type: 'personal', created_at: $now
            })
            CREATE (a:Account {
                id: $account_id, balance_cents: 0, currency: 'EUR',
                status: 'active', account_type: 'personal', created_at: $now
            })
            CREATE (u)-[:OWNS]->(a)
            """,
            user_id=user_id, name=body.name.strip(), email=email,
            password_hash=password_hash, account_id=account_id, now=now,
        )

    return RegisterResponse(
        message="Registration successful",
        user=UserResponse(
            id=user_id, name=body.name.strip(), email=email,
            role="user", status="active",
        ),
    )


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    with get_session() as session:
        result = session.run(
            "MATCH (u:User {email: $email}) RETURN u", email=body.email.lower()
        ).single()

    if result is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    user = dict(result["u"])

    if not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    if user["status"] == "disabled":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account has been disabled")
    if user["status"] == "frozen":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is frozen. Please contact support.")

    token = create_token(user["id"])
    return LoginResponse(access_token=token, role=user["role"])
