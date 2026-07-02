import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

import ledger
from dependencies import get_current_user
from games.mines import game, repository
from games.mines.schemas import (
    HistoryResponse, RevealRequest, RoundStateResponse, StartRoundRequest,
)

router = APIRouter(prefix="/games/mines", tags=["Mines"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_response(r: dict, reveal_mines: bool) -> RoundStateResponse:
    next_multiplier = None
    if r["status"] == "active":
        next_multiplier = game.multiplier_for(r["total_tiles"], r["mine_count"], len(r["revealed_tiles"]) + 1)
    return RoundStateResponse(
        round_id=r["id"], status=r["status"], total_tiles=r["total_tiles"], mine_count=r["mine_count"],
        revealed_tiles=r["revealed_tiles"], multiplier=r["multiplier"], next_multiplier=next_multiplier,
        payout_cents=r.get("payout_cents"),
        mine_positions=r["mine_positions"] if reveal_mines else None,
    )


@router.post("/start", response_model=RoundStateResponse)
def start_round(body: StartRoundRequest, current_user: dict = Depends(get_current_user)):
    try:
        game.validate_config(body.total_tiles, body.mine_count, body.bet_amount_cents)
    except game.InvalidMinesConfigError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    round_id = str(uuid.uuid4())
    try:
        ledger.place_wager(current_user["id"], body.bet_amount_cents, "mines", round_id)
    except ledger.InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    mine_positions = game.generate_mine_positions(body.total_tiles, body.mine_count)
    repository.create_round(
        round_id, current_user["id"], body.bet_amount_cents, body.total_tiles,
        body.mine_count, mine_positions, _now_iso(),
    )
    r = repository.get_round(round_id, current_user["id"])
    return _state_response(r, reveal_mines=False)


@router.get("/round/{round_id}", response_model=RoundStateResponse)
def get_round(round_id: str, current_user: dict = Depends(get_current_user)):
    r = repository.get_round(round_id, current_user["id"])
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    return _state_response(r, reveal_mines=r["status"] != "active")


@router.post("/round/{round_id}/reveal", response_model=RoundStateResponse)
def reveal_tile(round_id: str, body: RevealRequest, current_user: dict = Depends(get_current_user)):
    r = repository.get_round(round_id, current_user["id"])
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if r["status"] != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This round has already ended")
    if not (0 <= body.tile_index < r["total_tiles"]):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tile index out of range")
    if body.tile_index in r["revealed_tiles"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tile already revealed")

    if body.tile_index in r["mine_positions"]:
        # Bust: wager was already taken at start, nothing more to settle.
        repository.settle_round(round_id, "busted", None, _now_iso())
        r = repository.get_round(round_id, current_user["id"])
        return _state_response(r, reveal_mines=True)

    revealed = r["revealed_tiles"] + [body.tile_index]
    multiplier = game.multiplier_for(r["total_tiles"], r["mine_count"], len(revealed))
    repository.update_revealed(round_id, revealed, multiplier)
    r = repository.get_round(round_id, current_user["id"])
    return _state_response(r, reveal_mines=False)


@router.post("/round/{round_id}/cashout", response_model=RoundStateResponse)
def cashout(round_id: str, current_user: dict = Depends(get_current_user)):
    r = repository.get_round(round_id, current_user["id"])
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if r["status"] != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This round has already ended")
    if not r["revealed_tiles"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reveal at least one tile before cashing out")

    payout_cents = round(r["bet_amount_cents"] * r["multiplier"])
    try:
        _, new_balance, currency, _ = ledger.settle_payout(
            current_user["id"], payout_cents, "mines", round_id,
        )
    except ledger.InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    repository.settle_round(round_id, "cashed_out", payout_cents, _now_iso())
    r = repository.get_round(round_id, current_user["id"])
    return _state_response(r, reveal_mines=True)


@router.get("/history", response_model=HistoryResponse)
def history(current_user: dict = Depends(get_current_user)):
    return HistoryResponse(rounds=repository.get_history(current_user["id"]))
