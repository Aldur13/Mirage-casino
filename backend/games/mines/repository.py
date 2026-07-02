import json

from database import get_session


def create_round(round_id: str, user_id: str, bet_amount_cents: int, total_tiles: int,
                  mine_count: int, mine_positions: list[int], created_at: str) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (u:User {id: $user_id})
            CREATE (r:MinesRound {
                id: $round_id, user_id: $user_id, bet_amount_cents: $bet_amount_cents,
                total_tiles: $total_tiles, mine_count: $mine_count,
                mine_positions: $mine_positions, revealed_tiles: '[]',
                status: 'active', multiplier: 1.0, payout_cents: null, created_at: $created_at
            })
            CREATE (u)-[:PLAYED]->(r)
            """,
            round_id=round_id, user_id=user_id, bet_amount_cents=bet_amount_cents,
            total_tiles=total_tiles, mine_count=mine_count,
            mine_positions=json.dumps(mine_positions), created_at=created_at,
        )


def get_round(round_id: str, user_id: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            "MATCH (r:MinesRound {id: $round_id, user_id: $user_id}) RETURN r",
            round_id=round_id, user_id=user_id,
        ).single()
    if result is None:
        return None
    r = dict(result["r"])
    r["mine_positions"] = json.loads(r["mine_positions"])
    r["revealed_tiles"] = json.loads(r["revealed_tiles"])
    return r


def update_revealed(round_id: str, revealed_tiles: list[int], multiplier: float) -> None:
    with get_session() as session:
        session.run(
            "MATCH (r:MinesRound {id: $round_id}) SET r.revealed_tiles = $revealed, r.multiplier = $multiplier",
            round_id=round_id, revealed=json.dumps(revealed_tiles), multiplier=multiplier,
        )


def settle_round(round_id: str, status: str, payout_cents: int | None, ended_at: str) -> None:
    with get_session() as session:
        session.run(
            "MATCH (r:MinesRound {id: $round_id}) SET r.status = $status, r.payout_cents = $payout_cents, r.ended_at = $ended_at",
            round_id=round_id, status=status, payout_cents=payout_cents, ended_at=ended_at,
        )


def get_history(user_id: str, limit: int = 20) -> list[dict]:
    with get_session() as session:
        records = session.run(
            """
            MATCH (u:User {id: $user_id})-[:PLAYED]->(r:MinesRound)
            WHERE r.status <> 'active'
            RETURN r.id AS round_id, r.bet_amount_cents AS bet_amount_cents,
                   r.total_tiles AS total_tiles, r.mine_count AS mine_count,
                   r.multiplier AS multiplier, r.payout_cents AS payout_cents,
                   r.status AS status, r.created_at AS created_at, r.ended_at AS ended_at
            ORDER BY r.created_at DESC
            LIMIT $limit
            """,
            user_id=user_id, limit=limit,
        ).data()
    return records
