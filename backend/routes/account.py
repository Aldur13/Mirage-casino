from fastapi import APIRouter, Depends, HTTPException, status

from database import get_session
from dependencies import get_current_user
from ledger import InsufficientFundsError, place_wager, settle_payout
from models import (
    BalanceResponse, LedgerActionResponse, MeResponse,
    PayoutRequest, WagerRequest,
)

router = APIRouter()
dev_router = APIRouter()

_ACCOUNT_MATCH = """
    MATCH (u:User {id: $user_id})
    OPTIONAL MATCH (u)-[:OWNS]->(a1:Account)
    OPTIONAL MATCH (u)-[:MEMBER_OF]->(org:BusinessOrg)-[:HAS_ACCOUNT]->(a2:Account)
    WITH u, coalesce(a1, a2) AS a
    WHERE a IS NOT NULL
"""


@router.get("/me", response_model=MeResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    return MeResponse(
        id=current_user["id"],
        name=current_user["name"],
        email=current_user["email"],
        role=current_user.get("role", "user"),
        status=current_user["status"],
        account_type=current_user.get("account_type", "personal"),
    )


@router.get("/balance", response_model=BalanceResponse)
def get_balance(current_user: dict = Depends(get_current_user)):
    """Read-only view of the user's Mirage Bank Account — the casino has
    no wallet of its own, this balance IS the casino balance."""
    with get_session() as session:
        result = session.run(
            f"""
            {_ACCOUNT_MATCH}
            RETURN a.id AS account_id, a.balance_cents AS balance_cents,
                   a.currency AS currency, a.status AS status
            """,
            user_id=current_user["id"],
        ).single()

    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    return BalanceResponse(**dict(result))


# ── Dev-only ledger smoke-test routes ──────────────────────────────
# Exercise place_wager/settle_payout directly without a real game attached.
# Only mounted when app_env != "production" (see main.py) — real games will
# call ledger.py functions themselves, not go through HTTP for this.

@dev_router.post("/_dev/wager", response_model=LedgerActionResponse)
def dev_place_wager(body: WagerRequest, current_user: dict = Depends(get_current_user)):
    try:
        tx_id, new_balance, currency = place_wager(
            current_user["id"], body.amount_cents, body.game, body.round_id
        )
    except InsufficientFundsError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return LedgerActionResponse(transaction_id=tx_id, new_balance_cents=new_balance, currency=currency)


@dev_router.post("/_dev/payout", response_model=LedgerActionResponse)
def dev_settle_payout(body: PayoutRequest, current_user: dict = Depends(get_current_user)):
    try:
        tx_id, new_balance, currency, duplicate = settle_payout(
            current_user["id"], body.amount_cents, body.game, body.round_id
        )
    except InsufficientFundsError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    return LedgerActionResponse(
        transaction_id=tx_id, new_balance_cents=new_balance, currency=currency, duplicate=duplicate,
    )
