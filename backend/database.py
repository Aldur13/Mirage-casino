from neo4j import GraphDatabase
from config import settings

# Same system account mirage-bank's ledger uses — wagers/payouts move
# money between a user's Account and this Treasury node, exactly like
# bank withdrawals/deposits do.
TREASURY_ACCOUNT_ID = "TREASURY_ACCOUNT"

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
    return _driver


def close_driver():
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def get_session():
    return get_driver().session(database=settings.neo4j_database)


def setup_constraints():
    """Casino-specific constraints/indexes only.

    Bank's own constraints (User, Account, Transaction, ...) are already
    set up by mirage-bank against the same database — this only adds the
    casino's own node types on top.
    """
    with get_session() as session:
        constraints = [
            ("casino_profile_user_id_unique", "FOR (cp:CasinoProfile) REQUIRE cp.user_id IS UNIQUE"),
            ("wager_tx_id_unique", "FOR (t:WagerTransaction) REQUIRE t.id IS UNIQUE"),
            ("crash_round_id_unique", "FOR (r:CrashRound) REQUIRE r.id IS UNIQUE"),
            ("crash_round_nonce_unique", "FOR (r:CrashRound) REQUIRE r.nonce IS UNIQUE"),
            ("crash_bet_id_unique", "FOR (b:CrashBet) REQUIRE b.id IS UNIQUE"),
            ("mines_round_id_unique", "FOR (r:MinesRound) REQUIRE r.id IS UNIQUE"),
            ("blackjack_round_id_unique", "FOR (r:BlackjackRound) REQUIRE r.id IS UNIQUE"),
        ]
        for name, rule in constraints:
            session.run(f"CREATE CONSTRAINT {name} IF NOT EXISTS {rule}")

        indexes = [
            "FOR (t:WagerTransaction) ON (t.game, t.round_id)",
            "FOR (b:CrashBet) ON (b.round_id)",
            "FOR (r:CrashRound) ON (r.status)",
            "FOR (r:MinesRound) ON (r.user_id, r.status)",
            "FOR (r:BlackjackRound) ON (r.user_id, r.status)",
        ]
        for idx_body in indexes:
            session.run(f"CREATE INDEX IF NOT EXISTS {idx_body}")
