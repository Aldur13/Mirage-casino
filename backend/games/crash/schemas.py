from typing import Optional
from pydantic import BaseModel, Field


class BetSnapshot(BaseModel):
    display_name: str
    amount_cents: int
    auto_cashout_multiplier: Optional[float] = None
    cashout_multiplier: Optional[float] = None
    payout_cents: Optional[int] = None
    is_bot: bool


class CrashStateResponse(BaseModel):
    round_id: str
    status: str  # betting | running | crashed
    server_seed_hash: str
    nonce: int
    betting_closes_at: Optional[str] = None
    current_multiplier: Optional[float] = None
    crash_point: Optional[float] = None
    server_seed: Optional[str] = None
    bets: list[BetSnapshot]


class CrashHistoryItem(BaseModel):
    round_id: str
    nonce: int
    crash_point: float
    crashed_at: str


class CrashHistoryResponse(BaseModel):
    rounds: list[CrashHistoryItem]


class CrashVerifyResponse(BaseModel):
    round_id: str
    nonce: int
    server_seed: str
    server_seed_hash: str
    crash_point: float
    verified: bool


class PlaceBetRequest(BaseModel):
    amount_cents: int = Field(..., gt=0)
    auto_cashout_multiplier: Optional[float] = Field(None, ge=1.01, le=1000)
