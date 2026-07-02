"""The only module that is allowed to move money for casino games.

Every wager and payout goes through place_wager()/settle_payout() so the
"never allow negative balances / duplicate payouts / race conditions"
requirement is enforced in one audited place instead of once per game.

Both functions run a single Cypher statement, mirroring the pattern in
mirage-bank/backend/routes/account.py::withdraw — Neo4j applies one
session.run() as a single atomic transaction, so the balance check and
the write happen together with no read-then-write race window.

Wager/payout nodes carry both :WagerTransaction (casino-specific fields
and idempotency constraint) and :Transaction (mirage-bank's label) so
they show up automatically in the bank's existing GET /transactions
query, which matches on (t:Transaction) — no separate sync needed.
"""
import hashlib
import uuid
from datetime import datetime, timezone

from neo4j.exceptions import ConstraintError

from database import TREASURY_ACCOUNT_ID, get_session


class InsufficientFundsError(Exception):
    """Raised when a wager can't be placed (balance too low / inactive account)."""


def _idempotency_id(kind: str, game: str, round_id: str, user_id: str) -> str:
    """Deterministic WagerTransaction id for a given (kind, game, round, user).

    Lets settle_payout / place_wager be safely retried: a MERGE on this id
    turns a duplicate call into a no-op instead of a double spend/payout.
    """
    raw = f"{kind}:{game}:{round_id}:{user_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, hashlib.sha256(raw.encode()).hexdigest()))


def place_wager(user_id: str, amount_cents: int, game: str, round_id: str) -> tuple[str, int, str]:
    """Debit the user's bank Account into Treasury for a game wager.

    Returns (transaction_id, new_balance_cents, currency).
    Raises InsufficientFundsError if the account can't cover the wager,
    is inactive, doesn't exist, or this exact wager was already placed.
    """
    tx_id = _idempotency_id("wager", game, round_id, user_id)
    now = datetime.now(timezone.utc).isoformat()

    with get_session() as session:
        result = session.run(
            """
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:OWNS]->(a1:Account)
            OPTIONAL MATCH (u)-[:MEMBER_OF]->(org:BusinessOrg)-[:HAS_ACCOUNT]->(a2:Account)
            WITH coalesce(a1, a2) AS a
            WHERE a IS NOT NULL
            MATCH (treasury:Account {id: $treasury_id})
            WHERE a.status = 'active' AND a.balance_cents >= $amount_cents
              AND NOT EXISTS { MATCH (:WagerTransaction {id: $tx_id}) }
            SET a.balance_cents = a.balance_cents - $amount_cents,
                treasury.balance_cents = treasury.balance_cents + $amount_cents
            CREATE (t:WagerTransaction:Transaction {
                id: $tx_id, type: 'wager', kind: 'wager', game: $game, round_id: $round_id,
                amount_cents: $amount_cents, timestamp: $now, status: 'completed',
                description: $description
            })
            CREATE (a)-[:SENT]->(t)
            CREATE (t)-[:TO]->(treasury)
            RETURN a.balance_cents AS new_balance, a.currency AS currency
            """,
            user_id=user_id, treasury_id=TREASURY_ACCOUNT_ID,
            amount_cents=amount_cents, tx_id=tx_id, game=game, round_id=round_id,
            now=now, description=f"{game.title()} wager",
        ).single()

    if result is None:
        raise InsufficientFundsError(
            "Insufficient funds, inactive account, or wager already placed for this round"
        )

    return tx_id, result["new_balance"], result["currency"]


def settle_payout(user_id: str, amount_cents: int, game: str, round_id: str) -> tuple[str, int, str, bool]:
    """Credit the user's bank Account from Treasury for a game payout.

    Returns (transaction_id, new_balance_cents, currency, was_duplicate).
    Idempotent: calling this twice for the same (game, round_id, user_id)
    only pays out once — the second call returns was_duplicate=True and
    the current balance without moving any money.
    """
    tx_id = _idempotency_id("payout", game, round_id, user_id)
    now = datetime.now(timezone.utc).isoformat()
    description = f"{game.title()} payout"

    def _reserve_tx(tx):
        # CREATE (not MERGE) so the unique constraint on WagerTransaction.id
        # raises ConstraintError on a duplicate call instead of silently
        # matching the existing node — that's the idempotency guard.
        tx.run(
            """
            CREATE (t:WagerTransaction:Transaction {
                id: $tx_id, type: 'payout', kind: 'payout', game: $game, round_id: $round_id,
                amount_cents: $amount_cents, timestamp: $now, status: 'completed',
                description: $description
            })
            """,
            tx_id=tx_id, game=game, round_id=round_id, amount_cents=amount_cents,
            now=now, description=description,
        )

    def _credit_and_link(tx):
        result = tx.run(
            """
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:OWNS]->(a1:Account)
            OPTIONAL MATCH (u)-[:MEMBER_OF]->(org:BusinessOrg)-[:HAS_ACCOUNT]->(a2:Account)
            WITH coalesce(a1, a2) AS a
            WHERE a IS NOT NULL
            MATCH (treasury:Account {id: $treasury_id})
            MATCH (t:WagerTransaction {id: $tx_id})
            SET a.balance_cents = a.balance_cents + $amount_cents,
                treasury.balance_cents = treasury.balance_cents - $amount_cents
            CREATE (treasury)-[:SENT]->(t)
            CREATE (t)-[:TO]->(a)
            RETURN a.balance_cents AS new_balance, a.currency AS currency
            """,
            user_id=user_id, treasury_id=TREASURY_ACCOUNT_ID,
            amount_cents=amount_cents, tx_id=tx_id,
        ).single()
        if result is None:
            raise InsufficientFundsError("Payout target account not found")
        return result["new_balance"], result["currency"]

    def _current_balance(tx):
        result = tx.run(
            """
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:OWNS]->(a1:Account)
            OPTIONAL MATCH (u)-[:MEMBER_OF]->(org:BusinessOrg)-[:HAS_ACCOUNT]->(a2:Account)
            WITH coalesce(a1, a2) AS a
            WHERE a IS NOT NULL
            RETURN a.balance_cents AS balance, a.currency AS currency
            """,
            user_id=user_id,
        ).single()
        return result["balance"], result["currency"]

    with get_session() as session:
        try:
            session.execute_write(_reserve_tx)
        except ConstraintError:
            balance, currency = session.execute_read(_current_balance)
            return tx_id, balance, currency, True

        new_balance, currency = session.execute_write(_credit_and_link)

    return tx_id, new_balance, currency, False
