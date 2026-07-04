import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

import ledger
from dependencies import get_current_user
from games.crates import game, repository
from games.crates.schemas import (
    CrateDetailResponse, CrateItemView, CrateListResponse, CrateSummary,
    InventoryItemView, InventoryResponse, OpenCrateRequest, OpenCrateResponse,
    SellItemResponse,
)

router = APIRouter(prefix="/crates", tags=["Crates"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _inventory_view(item: dict) -> InventoryItemView:
    return InventoryItemView(**item)


@router.get("", response_model=CrateListResponse)
def list_crates():
    return CrateListResponse(crates=[CrateSummary(**c) for c in repository.list_crates()])


@router.get("/{crate_id}", response_model=CrateDetailResponse)
def get_crate(crate_id: str):
    crate = repository.get_crate_with_items(crate_id)
    if crate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crate not found")

    total_weight = sum(i["drop_weight"] for i in crate["items"])
    items = [
        CrateItemView(**i, drop_chance_pct=round(i["drop_weight"] / total_weight * 100, 2))
        for i in crate["items"]
    ]
    return CrateDetailResponse(
        id=crate["id"], name=crate["name"], price_cents=crate["price_cents"],
        description=crate["description"], items=items,
    )


@router.post("/{crate_id}/open", response_model=OpenCrateResponse)
def open_crate(
    crate_id: str,
    body: OpenCrateRequest = OpenCrateRequest(),
    current_user: dict = Depends(get_current_user),
):
    crate = repository.get_crate_with_items(crate_id)
    if crate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crate not found")
    if not crate["items"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This crate has no items configured")

    open_id = str(uuid.uuid4())
    try:
        _, new_balance, _ = ledger.place_wager(current_user["id"], crate["price_cents"], "crates", open_id)
    except ledger.InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    won_item = game.pick_weighted_item(crate["items"])
    inventory_item = repository.create_inventory_item(current_user["id"], won_item, _now_iso())

    if body.auto_sell:
        # Auto-sell settles through the same idempotent ledger path as a
        # manual sell (keyed on this inventory item's id), it just happens
        # immediately instead of waiting for the player to click Sell.
        try:
            _, new_balance, _, _ = ledger.settle_payout(
                current_user["id"], inventory_item["sell_value_cents"], "crates", f"sell:{inventory_item['id']}",
            )
        except ledger.InsufficientFundsError:
            # Payout target account missing — extremely unlikely (the wager
            # above just succeeded against the same account) but if it
            # happens, leave the item in inventory rather than losing it.
            return OpenCrateResponse(item=_inventory_view(inventory_item), new_balance_cents=new_balance)

        repository.mark_item_sold(inventory_item["id"], _now_iso())
        inventory_item = repository.get_inventory_item(inventory_item["id"], current_user["id"])
        return OpenCrateResponse(
            item=_inventory_view(inventory_item), new_balance_cents=new_balance,
            sold=True, payout_cents=inventory_item["sell_value_cents"],
        )

    return OpenCrateResponse(item=_inventory_view(inventory_item), new_balance_cents=new_balance)


@router.get("/inventory/mine", response_model=InventoryResponse)
def get_inventory(current_user: dict = Depends(get_current_user)):
    items = repository.get_inventory(current_user["id"])
    return InventoryResponse(items=[_inventory_view(i) for i in items])


@router.post("/inventory/{item_id}/sell", response_model=SellItemResponse)
def sell_item(item_id: str, current_user: dict = Depends(get_current_user)):
    item = repository.get_inventory_item(item_id, current_user["id"])
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    if item["status"] != "owned":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Item isn't available to sell")

    try:
        _, new_balance, _, _ = ledger.settle_payout(
            current_user["id"], item["sell_value_cents"], "crates", f"sell:{item_id}",
        )
    except ledger.InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    repository.mark_item_sold(item_id, _now_iso())
    item = repository.get_inventory_item(item_id, current_user["id"])

    return SellItemResponse(
        item=_inventory_view(item), payout_cents=item["sell_value_cents"], new_balance_cents=new_balance,
    )
