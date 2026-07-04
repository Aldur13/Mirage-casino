import json

from database import get_session


def create_round(round_id: str, user_id: str, bet_amount_cents: int, difficulty: str,
                  lane_outcomes: list[bool], created_at: str) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (u:User {id: $user_id})
            CREATE (r:ChickenRound {
                id: $round_id, user_id: $user_id, bet_amount_cents: $bet_amount_cents,
                difficulty: $difficulty, lane_outcomes: $lane_outcomes, lanes_crossed: 0,
                status: 'active', multiplier: 1.0, payout_cents: null, created_at: $created_at
            })
            CREATE (u)-[:PLAYED]->(r)
            """,
            round_id=round_id, user_id=user_id, bet_amount_cents=bet_amount_cents,
            difficulty=difficulty, lane_outcomes=json.dumps(lane_outcomes), created_at=created_at,
        )


def get_round(round_id: str, user_id: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            "MATCH (r:ChickenRound {id: $round_id, user_id: $user_id}) RETURN r",
            round_id=round_id, user_id=user_id,
        ).single()
    if result is None:
        return None
    r = dict(result["r"])
    r["lane_outcomes"] = json.loads(r["lane_outcomes"])
    return r


def update_progress(round_id: str, lanes_crossed: int, multiplier: float) -> None:
    with get_session() as session:
        session.run(
            "MATCH (r:ChickenRound {id: $round_id}) SET r.lanes_crossed = $lanes_crossed, r.multiplier = $multiplier",
            round_id=round_id, lanes_crossed=lanes_crossed, multiplier=multiplier,
        )


def settle_round(round_id: str, status: str, payout_cents: int | None, ended_at: str) -> None:
    with get_session() as session:
        session.run(
            "MATCH (r:ChickenRound {id: $round_id}) SET r.status = $status, r.payout_cents = $payout_cents, r.ended_at = $ended_at",
            round_id=round_id, status=status, payout_cents=payout_cents, ended_at=ended_at,
        )


def get_history(user_id: str, limit: int = 20) -> list[dict]:
    with get_session() as session:
        records = session.run(
            """
            MATCH (u:User {id: $user_id})-[:PLAYED]->(r:ChickenRound)
            WHERE r.status <> 'active'
            RETURN r.id AS round_id, r.bet_amount_cents AS bet_amount_cents,
                   r.difficulty AS difficulty, r.lanes_crossed AS lanes_crossed,
                   r.multiplier AS multiplier, r.payout_cents AS payout_cents,
                   r.status AS status, r.created_at AS created_at, r.ended_at AS ended_at
            ORDER BY r.created_at DESC
            LIMIT $limit
            """,
            user_id=user_id, limit=limit,
        ).data()
    return records
