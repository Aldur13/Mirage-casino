"""All Neo4j reads/writes for the Crash game live here — round_manager.py
drives the game logic and calls into this module rather than embedding
Cypher inline, matching the "keep backend modular" requirement.
"""
from database import get_session

CRASH_COUNTER_ID = "crash_nonce"


def next_nonce() -> int:
    """Atomically allocate the next round nonce. Never reused, even across
    server restarts, since it's persisted rather than kept in memory."""
    with get_session() as session:
        result = session.run(
            """
            MERGE (c:CrashCounter {id: $counter_id})
            ON CREATE SET c.value = 0
            SET c.value = c.value + 1
            RETURN c.value AS value
            """,
            counter_id=CRASH_COUNTER_ID,
        ).single()
    return result["value"]


def create_round(round_id: str, nonce: int, server_seed: str, server_seed_hash: str,
                  crash_point: float, betting_started_at: str) -> None:
    with get_session() as session:
        session.run(
            """
            CREATE (r:CrashRound {
                id: $round_id, nonce: $nonce, server_seed: $server_seed,
                server_seed_hash: $server_seed_hash, crash_point: $crash_point,
                status: 'betting', betting_started_at: $betting_started_at
            })
            """,
            round_id=round_id, nonce=nonce, server_seed=server_seed,
            server_seed_hash=server_seed_hash, crash_point=crash_point,
            betting_started_at=betting_started_at,
        )


def mark_round_running(round_id: str, running_started_at: str) -> None:
    with get_session() as session:
        session.run(
            "MATCH (r:CrashRound {id: $round_id}) SET r.status = 'running', r.running_started_at = $ts",
            round_id=round_id, ts=running_started_at,
        )


def mark_round_crashed(round_id: str, crashed_at: str) -> None:
    with get_session() as session:
        session.run(
            "MATCH (r:CrashRound {id: $round_id}) SET r.status = 'crashed', r.crashed_at = $ts",
            round_id=round_id, ts=crashed_at,
        )


def create_bet(bet_id: str, round_id: str, user_id: str | None, display_name: str,
                amount_cents: int, auto_cashout_multiplier: float | None,
                is_bot: bool, placed_at: str) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (r:CrashRound {id: $round_id})
            CREATE (b:CrashBet {
                id: $bet_id, round_id: $round_id, user_id: $user_id, display_name: $display_name,
                amount_cents: $amount_cents, auto_cashout_multiplier: $auto_cashout_multiplier,
                cashout_multiplier: null, payout_cents: null, status: 'active',
                is_bot: $is_bot, placed_at: $placed_at
            })
            CREATE (r)-[:HAS_BET]->(b)
            WITH b
            OPTIONAL MATCH (u:User {id: $user_id})
            FOREACH (_ IN CASE WHEN u IS NULL THEN [] ELSE [1] END | CREATE (u)-[:PLACED]->(b))
            """,
            bet_id=bet_id, round_id=round_id, user_id=user_id, display_name=display_name,
            amount_cents=amount_cents, auto_cashout_multiplier=auto_cashout_multiplier,
            is_bot=is_bot, placed_at=placed_at,
        )


def resolve_bet(bet_id: str, status: str, cashout_multiplier: float | None,
                 payout_cents: int | None) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (b:CrashBet {id: $bet_id})
            SET b.status = $status, b.cashout_multiplier = $cashout_multiplier,
                b.payout_cents = $payout_cents
            """,
            bet_id=bet_id, status=status,
            cashout_multiplier=cashout_multiplier, payout_cents=payout_cents,
        )


def get_recent_history(limit: int = 20) -> list[dict]:
    with get_session() as session:
        records = session.run(
            """
            MATCH (r:CrashRound {status: 'crashed'})
            RETURN r.id AS round_id, r.nonce AS nonce, r.crash_point AS crash_point,
                   r.crashed_at AS crashed_at
            ORDER BY r.crashed_at DESC
            LIMIT $limit
            """,
            limit=limit,
        ).data()
    return records


def get_round_for_verify(round_id: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            """
            MATCH (r:CrashRound {id: $round_id})
            RETURN r.nonce AS nonce, r.server_seed AS server_seed,
                   r.server_seed_hash AS server_seed_hash, r.crash_point AS crash_point,
                   r.status AS status
            """,
            round_id=round_id,
        ).single()
    return dict(result) if result else None
