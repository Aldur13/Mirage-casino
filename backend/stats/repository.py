"""Statistics are computed on read from the games' own data (WagerTransaction,
CrashBet, MinesRound, BlackjackRound, InventoryItem) rather than maintained
as a running counter — simpler to keep correct, and this project's data
volume doesn't need a materialized-stats table yet.
"""
import json

from database import get_session


def get_round_ledger_rows(user_id: str) -> list[dict]:
    """One row per (game, round_id): total wagered and total paid back.
    This is the base every wager/payout-derived stat is built from."""
    with get_session() as session:
        rows = session.run(
            """
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:OWNS]->(a:Account)
            WITH a WHERE a IS NOT NULL
            MATCH (a)-[:SENT]->(w:WagerTransaction {kind: 'wager'})
            WITH a, w.game AS game, w.round_id AS round_id, sum(w.amount_cents) AS wagered
            OPTIONAL MATCH (p:WagerTransaction {kind: 'payout', game: game, round_id: round_id})-[:TO]->(a)
            RETURN game, round_id, wagered, coalesce(sum(p.amount_cents), 0) AS paid
            """,
            user_id=user_id,
        ).data()
    return rows


def get_biggest_win_cents(user_id: str) -> int:
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:User {id: $user_id})-[:OWNS]->(a:Account)
            MATCH (p:WagerTransaction {kind: 'payout'})-[:TO]->(a)
            RETURN max(p.amount_cents) AS biggest_win
            """,
            user_id=user_id,
        ).single()
    return result["biggest_win"] or 0


def get_crash_stats(user_id: str) -> dict:
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:User {id: $user_id})-[:PLACED]->(b:CrashBet)
            RETURN count(b) AS played,
                   count(CASE WHEN b.status = 'cashed_out' THEN 1 END) AS won,
                   max(CASE WHEN b.status = 'cashed_out' THEN b.cashout_multiplier END) AS highest_multiplier
            """,
            user_id=user_id,
        ).single()
    return dict(result)


def get_mines_stats(user_id: str) -> dict:
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:User {id: $user_id})-[:PLAYED]->(r:MinesRound)
            WHERE r.status <> 'active'
            RETURN count(r) AS played, count(CASE WHEN r.status = 'cashed_out' THEN 1 END) AS cashouts
            """,
            user_id=user_id,
        ).single()
    return dict(result)


def get_blackjack_hands(user_id: str) -> list[dict]:
    """Blackjack round state is a JSON blob (see games/blackjack/repository.py)
    so per-hand outcomes aren't queryable in Cypher — pull settled rounds
    and tally outcomes in Python instead."""
    with get_session() as session:
        rows = session.run(
            """
            MATCH (u:User {id: $user_id})-[:PLAYED]->(r:BlackjackRound {status: 'settled'})
            RETURN r.state_json AS state_json
            """,
            user_id=user_id,
        ).data()
    hands = []
    for row in rows:
        state = json.loads(row["state_json"])
        hands.extend(state["hands"])
    return hands


def get_crates_stats(user_id: str) -> dict:
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:User {id: $user_id})-[:OWNS_ITEM]->(i:InventoryItem)
            RETURN count(i) AS opened, count(CASE WHEN i.rarity = 'legendary' THEN 1 END) AS legendary
            """,
            user_id=user_id,
        ).single()
    return dict(result)
