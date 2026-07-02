from typing import Optional
from pydantic import BaseModel, Field


class StartRoundRequest(BaseModel):
    bet_amount_cents: int = Field(..., gt=0)
    total_tiles: int = Field(25, ge=4, le=64)
    mine_count: int = Field(3, ge=1)


class RevealRequest(BaseModel):
    tile_index: int = Field(..., ge=0)


class RoundStateResponse(BaseModel):
    round_id: str
    status: str  # active | cashed_out | busted
    total_tiles: int
    mine_count: int
    revealed_tiles: list[int]
    multiplier: float
    next_multiplier: Optional[float] = None
    payout_cents: Optional[int] = None
    mine_positions: Optional[list[int]] = None  # only populated once status != active


class HistoryItem(BaseModel):
    round_id: str
    bet_amount_cents: int
    total_tiles: int
    mine_count: int
    multiplier: float
    payout_cents: Optional[int] = None
    status: str
    created_at: str
    ended_at: Optional[str] = None


class HistoryResponse(BaseModel):
    rounds: list[HistoryItem]
