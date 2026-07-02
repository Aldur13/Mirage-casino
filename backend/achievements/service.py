"""Achievements are evaluated lazily (whenever a caller asks) rather than
hooked into every game route — every game's own numbers already live in
Neo4j, so recomputing "does this player now qualify" is just a handful
of read queries, and unlocks are persisted (MERGE) so they never get
lost or re-evaluated away if a stat later drops (e.g. balance spent).
"""
from datetime import datetime, timezone

from achievements import repository
from achievements.definitions import ACHIEVEMENTS
from stats import repository as stats_repository


def _build_context(user_id: str) -> dict:
    rounds = stats_repository.get_round_ledger_rows(user_id)
    total_wagered = sum(r["wagered"] for r in rounds)
    total_paid = sum(r["paid"] for r in rounds)
    games_won = sum(1 for r in rounds if r["paid"] > r["wagered"])

    crash = stats_repository.get_crash_stats(user_id)
    mines = stats_repository.get_mines_stats(user_id)
    crates = stats_repository.get_crates_stats(user_id)
    bj_hands = stats_repository.get_blackjack_hands(user_id)
    blackjack_wins = sum(1 for h in bj_hands if h["outcome"] in ("win", "blackjack"))

    return {
        "games_played": len(rounds),
        "games_won": games_won,
        "total_profit_cents": total_paid - total_wagered,
        "balance_cents": repository.get_balance_cents(user_id),
        "biggest_single_wager_cents": repository.get_biggest_single_wager_cents(user_id),
        "blackjack_wins": blackjack_wins,
        "mines_cashouts": mines["cashouts"],
        "crash_games_played": crash["played"],
        "legendary_items_obtained": crates["legendary"],
    }


def check_and_unlock(user_id: str) -> list[dict]:
    """Returns the achievements newly unlocked by this call (empty if none)."""
    already_unlocked = repository.get_unlocked_ids(user_id)
    to_check = [a for a in ACHIEVEMENTS if a["id"] not in already_unlocked]
    if not to_check:
        return []

    context = _build_context(user_id)
    now = datetime.now(timezone.utc).isoformat()
    newly_unlocked = []
    for achievement in to_check:
        if achievement["check"](context):
            repository.unlock(user_id, achievement["id"], now)
            newly_unlocked.append(achievement)
    return newly_unlocked


def list_for_user(user_id: str) -> list[dict]:
    check_and_unlock(user_id)
    unlocked = repository.get_unlocked_ids(user_id)
    return [
        {"id": a["id"], "name": a["name"], "description": a["description"], "unlocked": a["id"] in unlocked}
        for a in ACHIEVEMENTS
    ]
