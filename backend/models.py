from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ── Auth (mirrors mirage-bank's shapes so both frontends can share a client) ──

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    status: str


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class MeResponse(BaseModel):
    id: str
    name: str
    email: str
    role: str
    status: str
    account_type: str = "personal"


# ── Balance (read-only view of the bank's Account — casino has no wallet) ──

class BalanceResponse(BaseModel):
    account_id: str
    balance_cents: int
    currency: str
    status: str


# ── Ledger (internal use by game modules, exposed via a dev-only test route) ──

class WagerRequest(BaseModel):
    amount_cents: int = Field(..., gt=0)
    game: str = Field(..., min_length=1, max_length=40)
    round_id: str = Field(..., min_length=1, max_length=100)


class PayoutRequest(BaseModel):
    amount_cents: int = Field(..., gt=0)
    game: str = Field(..., min_length=1, max_length=40)
    round_id: str = Field(..., min_length=1, max_length=100)


class LedgerActionResponse(BaseModel):
    transaction_id: Optional[str] = None
    new_balance_cents: int
    currency: str
    duplicate: bool = False
