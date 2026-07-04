import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

import ledger
from dependencies import get_current_user
from games.chicken import game, repository
from games.chicken.schemas import HistoryResponse, RoundStateResponse, StartRoundRequest

router = APIRouter(prefix="/games/chicken", tags=["Chicken"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_response(r: dict, reveal: bool) -> RoundStateResponse:
    next_multiplier = None
    if r["status"] == "active" and r["lanes_crossed"] < game.MAX_LANES:
        next_multiplier = game.multiplier_for(r["difficulty"], r["lanes_crossed"] + 1)
    return RoundStateResponse(
        round_id=r["id"], status=r["status"], difficulty=r["difficulty"],
        lanes_crossed=r["lanes_crossed"], max_lanes=game.MAX_LANES,
        multiplier=r["multiplier"], next_multiplier=next_multiplier,
        payout_cents=r.get("payout_cents"),
        lane_outcomes=r["lane_outcomes"] if reveal else None,
    )


@router.post("/start", response_model=RoundStateResponse)
def start_round(body: StartRoundRequest, current_user: dict = Depends(get_current_user)):
    try:
        game.validate_config(body.difficulty, body.bet_amount_cents)
    except game.InvalidChickenConfigError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    round_id = str(uuid.uuid4())
    try:
        ledger.place_wager(current_user["id"], body.bet_amount_cents, "chicken", round_id)
    except ledger.InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    lane_outcomes = game.generate_lane_outcomes(body.difficulty)
    repository.create_round(
        round_id, current_user["id"], body.bet_amount_cents, body.difficulty, lane_outcomes, _now_iso(),
    )
    r = repository.get_round(round_id, current_user["id"])
    return _state_response(r, reveal=False)


@router.get("/round/{round_id}", response_model=RoundStateResponse)
def get_round(round_id: str, current_user: dict = Depends(get_current_user)):
    r = repository.get_round(round_id, current_user["id"])
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    return _state_response(r, reveal=r["status"] != "active")


@router.post("/round/{round_id}/cross", response_model=RoundStateResponse)
def cross_lane(round_id: str, current_user: dict = Depends(get_current_user)):
    r = repository.get_round(round_id, current_user["id"])
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if r["status"] != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This round has already ended")
    if r["lanes_crossed"] >= game.MAX_LANES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already crossed every lane")

    lane_index = r["lanes_crossed"]
    if r["lane_outcomes"][lane_index]:
        # Hit: wager was already taken at start, nothing more to settle.
        repository.settle_round(round_id, "busted", None, _now_iso())
        r = repository.get_round(round_id, current_user["id"])
        return _state_response(r, reveal=True)

    lanes_crossed = lane_index + 1
    multiplier = game.multiplier_for(r["difficulty"], lanes_crossed)
    repository.update_progress(round_id, lanes_crossed, multiplier)
    r = repository.get_round(round_id, current_user["id"])
    return _state_response(r, reveal=False)


@router.post("/round/{round_id}/cashout", response_model=RoundStateResponse)
def cashout(round_id: str, current_user: dict = Depends(get_current_user)):
    r = repository.get_round(round_id, current_user["id"])
    if r is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if r["status"] != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This round has already ended")
    if r["lanes_crossed"] < 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cross at least one lane before cashing out")

    payout_cents = round(r["bet_amount_cents"] * r["multiplier"])
    try:
        _, new_balance, currency, _ = ledger.settle_payout(
            current_user["id"], payout_cents, "chicken", round_id,
        )
    except ledger.InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    repository.settle_round(round_id, "cashed_out", payout_cents, _now_iso())
    r = repository.get_round(round_id, current_user["id"])
    return _state_response(r, reveal=True)


@router.get("/history", response_model=HistoryResponse)
def history(current_user: dict = Depends(get_current_user)):
    return HistoryResponse(rounds=repository.get_history(current_user["id"]))
