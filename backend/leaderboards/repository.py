from database import get_session

DEFAULT_LIMIT = 10


def richest_players(limit: int = DEFAULT_LIMIT) -> list[dict]:
    with get_session() as session:
        return session.run(
            """
            MATCH (u:User)-[:OWNS]->(a:Account)
            WHERE a.status = 'active'
            RETURN u.id AS user_id, u.name AS name, a.balance_cents AS balance_cents
            ORDER BY a.balance_cents DESC
            LIMIT $limit
            """,
            limit=limit,
        ).data()


def biggest_wins(limit: int = DEFAULT_LIMIT) -> list[dict]:
    with get_session() as session:
        return session.run(
            """
            MATCH (p:WagerTransaction {kind: 'payout'})-[:TO]->(a:Account)<-[:OWNS]-(u:User)
            RETURN u.id AS user_id, u.name AS name, p.amount_cents AS amount_cents,
                   p.game AS game, p.timestamp AS timestamp
            ORDER BY p.amount_cents DESC
            LIMIT $limit
            """,
            limit=limit,
        ).data()


_PROFIT_QUERY_ALL_TIME = """
    MATCH (u:User)-[:OWNS]->(a:Account)
    OPTIONAL MATCH (a)-[:SENT]->(w:WagerTransaction {kind: 'wager'})
    WITH u, a, coalesce(sum(w.amount_cents), 0) AS wagered
    OPTIONAL MATCH (p:WagerTransaction {kind: 'payout'})-[:TO]->(a)
    WITH u, wagered, coalesce(sum(p.amount_cents), 0) AS paid
    RETURN u.id AS user_id, u.name AS name, wagered AS wagered_cents, (paid - wagered) AS profit_cents
    ORDER BY profit_cents DESC
    LIMIT $limit
"""

_PROFIT_QUERY_SINCE = """
    MATCH (u:User)-[:OWNS]->(a:Account)
    OPTIONAL MATCH (a)-[:SENT]->(w:WagerTransaction {kind: 'wager'})
        WHERE w.timestamp >= $since
    WITH u, a, coalesce(sum(w.amount_cents), 0) AS wagered
    OPTIONAL MATCH (p:WagerTransaction {kind: 'payout'})-[:TO]->(a)
        WHERE p.timestamp >= $since
    WITH u, wagered, coalesce(sum(p.amount_cents), 0) AS paid
    RETURN u.id AS user_id, u.name AS name, wagered AS wagered_cents, (paid - wagered) AS profit_cents
    ORDER BY profit_cents DESC
    LIMIT $limit
"""


def most_profit(limit: int = DEFAULT_LIMIT, since: str | None = None) -> list[dict]:
    query = _PROFIT_QUERY_SINCE if since else _PROFIT_QUERY_ALL_TIME
    with get_session() as session:
        return session.run(query, limit=limit, since=since).data()


def most_wagered(limit: int = DEFAULT_LIMIT) -> list[dict]:
    with get_session() as session:
        return session.run(
            """
            MATCH (u:User)-[:OWNS]->(a:Account)
            MATCH (a)-[:SENT]->(w:WagerTransaction {kind: 'wager'})
            WITH u, sum(w.amount_cents) AS wagered_cents
            RETURN u.id AS user_id, u.name AS name, wagered_cents
            ORDER BY wagered_cents DESC
            LIMIT $limit
            """,
            limit=limit,
        ).data()


def most_games_played(limit: int = DEFAULT_LIMIT) -> list[dict]:
    with get_session() as session:
        return session.run(
            """
            MATCH (u:User)-[:OWNS]->(a:Account)
            MATCH (a)-[:SENT]->(w:WagerTransaction {kind: 'wager'})
            WITH u, w.game AS game, w.round_id AS round_id
            WITH u, count(*) AS games_played
            RETURN u.id AS user_id, u.name AS name, games_played
            ORDER BY games_played DESC
            LIMIT $limit
            """,
            limit=limit,
        ).data()


def biggest_crash_cashouts(limit: int = DEFAULT_LIMIT) -> list[dict]:
    with get_session() as session:
        return session.run(
            """
            MATCH (u:User)-[:PLACED]->(b:CrashBet {status: 'cashed_out'})
            RETURN u.id AS user_id, u.name AS name, b.payout_cents AS payout_cents,
                   b.cashout_multiplier AS multiplier
            ORDER BY b.payout_cents DESC
            LIMIT $limit
            """,
            limit=limit,
        ).data()


def most_legendary_items(limit: int = DEFAULT_LIMIT) -> list[dict]:
    with get_session() as session:
        return session.run(
            """
            MATCH (u:User)-[:OWNS_ITEM]->(i:InventoryItem {rarity: 'legendary'})
            WITH u, count(i) AS legendary_count
            RETURN u.id AS user_id, u.name AS name, legendary_count
            ORDER BY legendary_count DESC
            LIMIT $limit
            """,
            limit=limit,
        ).data()
