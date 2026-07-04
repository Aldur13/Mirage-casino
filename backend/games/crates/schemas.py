from typing import Optional
from pydantic import BaseModel


class CrateSummary(BaseModel):
    id: str
    name: str
    price_cents: int
    description: str


class CrateItemView(BaseModel):
    id: str
    name: str
    rarity: str
    value_cents: int
    sell_value_cents: int
    image_url: str
    description: str
    drop_weight: int
    drop_chance_pct: float


class CrateDetailResponse(BaseModel):
    id: str
    name: str
    price_cents: int
    description: str
    items: list[CrateItemView]


class CrateListResponse(BaseModel):
    crates: list[CrateSummary]


class InventoryItemView(BaseModel):
    id: str
    name: str
    rarity: str
    value_cents: int
    sell_value_cents: int
    image_url: str
    obtained_at: str
    status: str
    sold_at: Optional[str] = None


class InventoryResponse(BaseModel):
    items: list[InventoryItemView]


class OpenCrateRequest(BaseModel):
    auto_sell: bool = False


class OpenCrateResponse(BaseModel):
    item: InventoryItemView
    new_balance_cents: int
    sold: bool = False
    payout_cents: Optional[int] = None


class SellItemResponse(BaseModel):
    item: InventoryItemView
    payout_cents: int
    new_balance_cents: int
