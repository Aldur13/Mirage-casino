import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

import ledger
from dependencies import get_current_user
from games.blackjack import deck, game, repository
from games.blackjack.schemas import (
    HistoryResponse, InsuranceRequest, RoundStateResponse, StartRequest,
)

router = APIRouter(prefix="/games/blackjack", tags=["Blackjack"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_hand(cards: list[dict], bet_cents: int, ledger_round_id: str) -> dict:
    return {
        "cards": cards, "bet_cents": bet_cents, "status": "active",
        "outcome": None, "payout_cents": None, "ledger_round_id": ledger_round_id,
        "doubled": False,
    }


def _peek_condition(dealer_up_card: dict) -> bool:
    return dealer_up_card["rank"] in ("A", "10", "J", "Q", "K")


def _settle_non_bust_hands(state: dict, user_id: str) -> int:
    """Reveal the dealer's hand, let the dealer play, settle every hand
    that isn't already busted, and return the total paid out."""
    state["dealer_hidden"] = False
    while game.dealer_should_hit(state["dealer_cards"]):
        state["dealer_cards"].append(deck.draw(state["shoe"]))

    total_payout = 0
    for hand in state["hands"]:
        if hand["status"] == "busted":
            hand["outcome"] = "bust"
            hand["payout_cents"] = 0
            continue

        had_blackjack = hand["status"] == "blackjack"
        outcome, payout_cents = game.settle_hand(
            hand["cards"], state["dealer_cards"], hand["bet_cents"], had_blackjack,
        )
        hand["outcome"] = outcome
        hand["payout_cents"] = payout_cents
        total_payout += payout_cents

        if payout_cents > 0:
            ledger.settle_payout(user_id, payout_cents, "blackjack", hand["ledger_round_id"])

    state["phase"] = "settled"
    return total_payout


def _advance_or_settle(state: dict, user_id: str) -> None:
    """Called whenever the active hand is done (stood/busted/doubled).
    Moves to the next split hand, or — if every hand is done — plays out
    the dealer and settles."""
    if state["active_hand_index"] < len(state["hands"]) - 1:
        state["active_hand_index"] += 1
        return

    if all(h["status"] in ("busted",) for h in state["hands"]):
        # Every hand busted — dealer doesn't need to draw, nothing to compare.
        state["dealer_hidden"] = False
        for hand in state["hands"]:
            hand["outcome"] = "bust"
            hand["payout_cents"] = 0
        state["phase"] = "settled"
        return

    _settle_non_bust_hands(state, user_id)


def _hand_view(hand: dict) -> dict:
    value, is_soft = game.hand_value(hand["cards"])
    return {**hand, "value": value, "is_soft": is_soft}


def _state_response(round_id: str, state: dict) -> RoundStateResponse:
    active_hand = state["hands"][state["active_hand_index"]] if state["phase"] == "player_turn" else None
    can_double = bool(active_hand and len(active_hand["cards"]) == 2 and active_hand["status"] == "active")
    can_split = bool(
        active_hand and len(state["hands"]) == 1 and active_hand["status"] == "active"
        and game.can_split(active_hand["cards"])
    )
    total_payout = None
    if state["phase"] == "settled":
        total_payout = sum(h["payout_cents"] or 0 for h in state["hands"])

    visible_dealer_cards = state["dealer_cards"] if not state["dealer_hidden"] else state["dealer_cards"][:1]

    return RoundStateResponse(
        round_id=round_id, phase=state["phase"], hands=[_hand_view(h) for h in state["hands"]],
        active_hand_index=state["active_hand_index"],
        dealer_cards=visible_dealer_cards,
        dealer_hidden=state["dealer_hidden"],
        dealer_value=game.hand_value(visible_dealer_cards)[0],
        insurance_available=state["phase"] == "insurance_pending",
        insurance_bet_cents=state.get("insurance_bet_cents"),
        insurance_outcome=state.get("insurance_outcome"),
        can_double=can_double, can_split=can_split, total_payout_cents=total_payout,
    )


@router.post("/start", response_model=RoundStateResponse)
def start_round(body: StartRequest, current_user: dict = Depends(get_current_user)):
    if body.bet_amount_cents < game.MIN_BET_CENTS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                             detail=f"Minimum bet is {game.MIN_BET_CENTS} cents")

    round_id = str(uuid.uuid4())
    try:
        ledger.place_wager(current_user["id"], body.bet_amount_cents, "blackjack", round_id)
    except ledger.InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    shoe = deck.new_shoe()
    player_cards = [deck.draw(shoe), deck.draw(shoe)]
    dealer_cards = [deck.draw(shoe), deck.draw(shoe)]

    state = {
        "shoe": shoe,
        "dealer_cards": dealer_cards,
        "dealer_hidden": True,
        "hands": [_new_hand(player_cards, body.bet_amount_cents, round_id)],
        "active_hand_index": 0,
        "insurance_bet_cents": None,
        "insurance_outcome": None,
        "phase": "player_turn",
    }

    if dealer_cards[0]["rank"] == "A":
        state["phase"] = "insurance_pending"
    else:
        _resolve_initial_blackjacks(state, current_user["id"])

    repository.create_round(round_id, current_user["id"], state, _now_iso())
    return _state_response(round_id, state)


def _resolve_initial_blackjacks(state: dict, user_id: str) -> None:
    hand = state["hands"][0]
    player_bj = game.is_blackjack(hand["cards"])
    dealer_bj = _peek_condition(state["dealer_cards"][0]) and game.is_blackjack(state["dealer_cards"])

    if not player_bj and not dealer_bj:
        return

    hand["status"] = "blackjack" if player_bj else hand["status"]
    if dealer_bj:
        state["dealer_hidden"] = False
        if player_bj:
            hand["outcome"], hand["payout_cents"] = "push", hand["bet_cents"]
        else:
            hand["outcome"], hand["payout_cents"] = "loss", 0
        if hand["payout_cents"]:
            ledger.settle_payout(user_id, hand["payout_cents"], "blackjack", hand["ledger_round_id"])
        state["phase"] = "settled"
    elif player_bj:
        state["dealer_hidden"] = False
        hand["outcome"], hand["payout_cents"] = "blackjack", round(hand["bet_cents"] * 2.5)
        ledger.settle_payout(user_id, hand["payout_cents"], "blackjack", hand["ledger_round_id"])
        state["phase"] = "settled"


@router.get("/round/{round_id}", response_model=RoundStateResponse)
def get_round(round_id: str, current_user: dict = Depends(get_current_user)):
    state = repository.get_round(round_id, current_user["id"])
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    return _state_response(round_id, state)


@router.post("/round/{round_id}/insurance", response_model=RoundStateResponse)
def insurance(round_id: str, body: InsuranceRequest, current_user: dict = Depends(get_current_user)):
    state = repository.get_round(round_id, current_user["id"])
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if state["phase"] != "insurance_pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Insurance isn't available right now")

    if body.want:
        insurance_bet = round(state["hands"][0]["bet_cents"] / 2)
        try:
            ledger.place_wager(current_user["id"], insurance_bet, "blackjack", f"{round_id}:insurance")
        except ledger.InsufficientFundsError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        state["insurance_bet_cents"] = insurance_bet

        if game.is_blackjack(state["dealer_cards"]):
            payout = insurance_bet * 3
            ledger.settle_payout(current_user["id"], payout, "blackjack", f"{round_id}:insurance")
            state["insurance_outcome"] = "win"
        else:
            state["insurance_outcome"] = "loss"
    else:
        state["insurance_outcome"] = None

    state["phase"] = "player_turn"
    _resolve_initial_blackjacks(state, current_user["id"])
    repository.save_state(round_id, state, _now_iso() if state["phase"] == "settled" else None)
    return _state_response(round_id, state)


@router.post("/round/{round_id}/hit", response_model=RoundStateResponse)
def hit(round_id: str, current_user: dict = Depends(get_current_user)):
    state = repository.get_round(round_id, current_user["id"])
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if state["phase"] != "player_turn":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active hand to act on")

    hand = state["hands"][state["active_hand_index"]]
    hand["cards"].append(deck.draw(state["shoe"]))
    if game.is_bust(hand["cards"]):
        hand["status"] = "busted"
        _advance_or_settle(state, current_user["id"])

    repository.save_state(round_id, state, _now_iso() if state["phase"] == "settled" else None)
    return _state_response(round_id, state)


@router.post("/round/{round_id}/stand", response_model=RoundStateResponse)
def stand(round_id: str, current_user: dict = Depends(get_current_user)):
    state = repository.get_round(round_id, current_user["id"])
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if state["phase"] != "player_turn":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active hand to act on")

    state["hands"][state["active_hand_index"]]["status"] = "stood"
    _advance_or_settle(state, current_user["id"])

    repository.save_state(round_id, state, _now_iso() if state["phase"] == "settled" else None)
    return _state_response(round_id, state)


@router.post("/round/{round_id}/double", response_model=RoundStateResponse)
def double(round_id: str, current_user: dict = Depends(get_current_user)):
    state = repository.get_round(round_id, current_user["id"])
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if state["phase"] != "player_turn":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active hand to act on")

    hand = state["hands"][state["active_hand_index"]]
    if len(hand["cards"]) != 2:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Can only double on the first two cards")

    try:
        ledger.place_wager(current_user["id"], hand["bet_cents"], "blackjack", f"{hand['ledger_round_id']}:double")
    except ledger.InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    hand["bet_cents"] *= 2
    hand["doubled"] = True
    hand["cards"].append(deck.draw(state["shoe"]))
    hand["status"] = "busted" if game.is_bust(hand["cards"]) else "doubled"
    _advance_or_settle(state, current_user["id"])

    repository.save_state(round_id, state, _now_iso() if state["phase"] == "settled" else None)
    return _state_response(round_id, state)


@router.post("/round/{round_id}/split", response_model=RoundStateResponse)
def split(round_id: str, current_user: dict = Depends(get_current_user)):
    state = repository.get_round(round_id, current_user["id"])
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if state["phase"] != "player_turn":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active hand to act on")
    if len(state["hands"]) != 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already split this round")

    hand = state["hands"][0]
    if not game.can_split(hand["cards"]):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hand isn't splittable")

    split_round_id = f"{round_id}:split"
    try:
        ledger.place_wager(current_user["id"], hand["bet_cents"], "blackjack", split_round_id)
    except ledger.InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    card_a, card_b = hand["cards"]
    hand["cards"] = [card_a, deck.draw(state["shoe"])]
    second_hand = _new_hand([card_b, deck.draw(state["shoe"])], hand["bet_cents"], split_round_id)
    state["hands"].append(second_hand)

    repository.save_state(round_id, state)
    return _state_response(round_id, state)


@router.get("/history", response_model=HistoryResponse)
def history(current_user: dict = Depends(get_current_user)):
    return HistoryResponse(rounds=repository.get_history(current_user["id"]))
