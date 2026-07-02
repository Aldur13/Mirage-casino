import json

from database import get_session


def create_round(round_id: str, user_id: str, state: dict, created_at: str) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (u:User {id: $user_id})
            CREATE (r:BlackjackRound {
                id: $round_id, user_id: $user_id, state_json: $state_json,
                status: $status, bet_amount_cents: $bet_amount_cents, created_at: $created_at
            })
            CREATE (u)-[:PLAYED]->(r)
            """,
            round_id=round_id, user_id=user_id, state_json=json.dumps(state),
            status=state["phase"], bet_amount_cents=state["hands"][0]["bet_cents"], created_at=created_at,
        )


def get_round(round_id: str, user_id: str) -> dict | None:
    with get_session() as session:
        result = session.run(
            "MATCH (r:BlackjackRound {id: $round_id, user_id: $user_id}) RETURN r",
            round_id=round_id, user_id=user_id,
        ).single()
    if result is None:
        return None
    r = dict(result["r"])
    state = json.loads(r["state_json"])
    return state


def save_state(round_id: str, state: dict, ended_at: str | None = None) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (r:BlackjackRound {id: $round_id})
            SET r.state_json = $state_json, r.status = $status, r.ended_at = coalesce($ended_at, r.ended_at)
            """,
            round_id=round_id, state_json=json.dumps(state), status=state["phase"], ended_at=ended_at,
        )


def get_history(user_id: str, limit: int = 20) -> list[dict]:
    with get_session() as session:
        records = session.run(
            """
            MATCH (u:User {id: $user_id})-[:PLAYED]->(r:BlackjackRound)
            WHERE r.status = 'settled'
            RETURN r.id AS round_id, r.bet_amount_cents AS bet_amount_cents,
                   r.status AS status, r.created_at AS created_at, r.ended_at AS ended_at
            ORDER BY r.created_at DESC
            LIMIT $limit
            """,
            user_id=user_id, limit=limit,
        ).data()
    return records
