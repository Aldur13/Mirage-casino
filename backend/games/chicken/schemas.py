from typing import Optional
from pydantic import BaseModel, Field


class StartRoundRequest(BaseModel):
    bet_amount_cents: int = Field(..., gt=0)
    difficulty: str = Field("medium", pattern=r"^(easy|medium|hard|daredevil)$")


class RoundStateResponse(BaseModel):
    round_id: str
    status: str  # active | cashed_out | busted
    difficulty: str
    lanes_crossed: int
    max_lanes: int
    multiplier: float
    next_multiplier: Optional[float] = None
    payout_cents: Optional[int] = None
    lane_outcomes: Optional[list[bool]] = None  # only populated once status != active


class HistoryItem(BaseModel):
    round_id: str
    bet_amount_cents: int
    difficulty: str
    lanes_crossed: int
    multiplier: float
    payout_cents: Optional[int] = None
    status: str
    created_at: str
    ended_at: Optional[str] = None


class HistoryResponse(BaseModel):
    rounds: list[HistoryItem]
