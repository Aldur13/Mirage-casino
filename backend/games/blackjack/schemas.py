from typing import Optional
from pydantic import BaseModel, Field


class StartRequest(BaseModel):
    bet_amount_cents: int = Field(..., gt=0)


class InsuranceRequest(BaseModel):
    want: bool


class HandView(BaseModel):
    cards: list[dict]
    bet_cents: int
    status: str  # active | stood | busted | blackjack | doubled
    outcome: Optional[str] = None
    payout_cents: Optional[int] = None
    value: int
    is_soft: bool = False


class RoundStateResponse(BaseModel):
    round_id: str
    phase: str  # insurance_pending | player_turn | settled
    hands: list[HandView]
    active_hand_index: int
    dealer_cards: list[dict]
    dealer_hidden: bool
    dealer_value: Optional[int] = None
    insurance_available: bool
    insurance_bet_cents: Optional[int] = None
    insurance_outcome: Optional[str] = None
    can_double: bool = False
    can_split: bool = False
    total_payout_cents: Optional[int] = None


class HistoryItem(BaseModel):
    round_id: str
    bet_amount_cents: int
    status: str
    created_at: str
    ended_at: Optional[str] = None


class HistoryResponse(BaseModel):
    rounds: list[HistoryItem]
