import asyncio

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from dependencies import get_ws_user
from games.crash import provably_fair, repository
from games.crash.connection_manager import manager
from games.crash.round_manager import BetRejectedError, round_manager
from games.crash.schemas import (
    CrashHistoryResponse, CrashStateResponse, CrashVerifyResponse,
)

router = APIRouter(prefix="/games/crash", tags=["Crash"])


def _parse_auto_cashout(raw) -> float | None:
    """Validate the client-supplied auto-cashout target before it reaches
    the shared round loop. An unvalidated string/negative here would raise
    mid-tick inside _resolve_auto_cashouts and restart the round for every
    connected player, so reject it as a per-client error instead."""
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError("auto_cashout_multiplier must be a number")
    if value <= 1.0:
        raise ValueError("auto_cashout_multiplier must be greater than 1.0")
    return value


@router.get("/state", response_model=CrashStateResponse)
def get_state():
    """Snapshot of the current round — lets a page render something
    sensible before its WebSocket connection finishes opening."""
    return round_manager.public_state()


@router.get("/history", response_model=CrashHistoryResponse)
def get_history():
    rounds = repository.get_recent_history(limit=20)
    return CrashHistoryResponse(rounds=rounds)


@router.get("/verify/{round_id}", response_model=CrashVerifyResponse)
def verify_round(round_id: str):
    """Provably-fair check: recompute the crash point from the revealed
    seed and confirm it matches what was published before the round ran."""
    round_data = repository.get_round_for_verify(round_id)
    if round_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Round not found")
    if round_data["status"] != "crashed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Round hasn't crashed yet — server_seed is still hidden",
        )

    verified = provably_fair.verify(
        round_data["server_seed"], round_data["nonce"],
        round_data["server_seed_hash"], round_data["crash_point"],
    )
    return CrashVerifyResponse(
        round_id=round_id, nonce=round_data["nonce"], server_seed=round_data["server_seed"],
        server_seed_hash=round_data["server_seed_hash"], crash_point=round_data["crash_point"],
        verified=verified,
    )


@router.websocket("/ws")
async def crash_ws(websocket: WebSocket, token: str | None = Query(default=None)):
    # A connection without a token is a spectator: it receives every
    # broadcast but any place_bet/cashout attempt is rejected below.
    user = await asyncio.to_thread(get_ws_user, token)

    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "state", **round_manager.public_state()})

        while True:
            message = await websocket.receive_json()
            action = message.get("action")

            if action == "place_bet":
                if user is None:
                    await websocket.send_json({"type": "error", "message": "Log in to place a bet"})
                    continue
                try:
                    amount_cents = int(message.get("amount_cents", 0))
                    auto_cashout_multiplier = _parse_auto_cashout(
                        message.get("auto_cashout_multiplier")
                    )
                    await round_manager.place_bet(
                        user_id=user["id"],
                        display_name=user["name"],
                        amount_cents=amount_cents,
                        auto_cashout_multiplier=auto_cashout_multiplier,
                    )
                except (BetRejectedError, TypeError, ValueError) as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})

            elif action == "cashout":
                if user is None:
                    await websocket.send_json({"type": "error", "message": "Log in to cash out"})
                    continue
                try:
                    await round_manager.cashout(user["id"])
                except BetRejectedError as exc:
                    await websocket.send_json({"type": "error", "message": str(exc)})

            else:
                await websocket.send_json({"type": "error", "message": f"Unknown action: {action!r}"})

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
