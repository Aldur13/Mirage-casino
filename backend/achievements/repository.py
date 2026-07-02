from database import get_session


def get_unlocked_ids(user_id: str) -> set[str]:
    with get_session() as session:
        rows = session.run(
            "MATCH (u:User {id: $user_id})-[:UNLOCKED]->(a:Achievement) RETURN a.id AS id",
            user_id=user_id,
        ).data()
    return {r["id"] for r in rows}


def unlock(user_id: str, achievement_id: str, unlocked_at: str) -> None:
    with get_session() as session:
        session.run(
            """
            MATCH (u:User {id: $user_id})
            MERGE (a:Achievement {id: $achievement_id})
            MERGE (u)-[r:UNLOCKED]->(a)
            ON CREATE SET r.unlocked_at = $unlocked_at
            """,
            user_id=user_id, achievement_id=achievement_id, unlocked_at=unlocked_at,
        )


def get_balance_cents(user_id: str) -> int:
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:User {id: $user_id})
            OPTIONAL MATCH (u)-[:OWNS]->(a1:Account)
            OPTIONAL MATCH (u)-[:MEMBER_OF]->(org:BusinessOrg)-[:HAS_ACCOUNT]->(a2:Account)
            WITH coalesce(a1, a2) AS a
            RETURN a.balance_cents AS balance_cents
            """,
            user_id=user_id,
        ).single()
    return (result["balance_cents"] if result else None) or 0


def get_biggest_single_wager_cents(user_id: str) -> int:
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:User {id: $user_id})-[:OWNS]->(a:Account)
            MATCH (a)-[:SENT]->(w:WagerTransaction {kind: 'wager'})
            RETURN max(w.amount_cents) AS biggest
            """,
            user_id=user_id,
        ).single()
    return (result["biggest"] if result else None) or 0
