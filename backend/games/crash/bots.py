"""Simulated players that fill a quiet room without touching real money.

Bots never call ledger.py — they carry an in-memory-only virtual bankroll
that exists for the lifetime of one round and is never persisted. Every
payload that describes a bot includes is_bot=True so the frontend can
badge them; they are never presented as indistinguishable from a real
user (see the Phase 1 plan's bot policy decision).
"""
import random
import uuid

MIN_ACTIVE_REAL_PLAYERS = 4  # below this, bots top the room up
MIN_BOTS_PER_ROUND = 2
MAX_BOTS_PER_ROUND = 7

_FIRST_NAMES = [
    "Liam", "Emma", "Noah", "Olivia", "Ava", "Ethan", "Sophia", "Mason",
    "Isabella", "Lucas", "Mia", "Logan", "Amelia", "Elijah", "Harper",
    "James", "Evelyn", "Benjamin", "Abigail", "Henry", "Ella", "Alex",
    "Grace", "Daniel", "Chloe", "Matthew", "Zoe", "Jack", "Lily", "Owen",
]
_LAST_INITIALS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _random_display_name() -> str:
    return f"{random.choice(_FIRST_NAMES)} {random.choice(_LAST_INITIALS)}."


class BotPlayer:
    """One bot's state for a single round. Discarded after the round ends."""

    def __init__(self):
        self.id = f"bot-{uuid.uuid4()}"
        self.display_name = _random_display_name()
        self.bankroll_cents = random.randint(1_000, 5_000_000)
        self.amount_cents = min(
            self.bankroll_cents,
            random.randint(100, 200_000),
        )
        # Most bots cash out early/moderate; a few go high-risk — mirrors
        # typical real-player behavior so the room doesn't look scripted.
        roll = random.random()
        if roll < 0.6:
            self.auto_cashout_multiplier = round(random.uniform(1.2, 2.5), 2)
        elif roll < 0.9:
            self.auto_cashout_multiplier = round(random.uniform(2.5, 5.0), 2)
        else:
            self.auto_cashout_multiplier = round(random.uniform(5.0, 20.0), 2)


def maybe_spawn_bots(active_real_players: int) -> list[BotPlayer]:
    """Top the room up with bots if real attendance is low this round."""
    if active_real_players >= MIN_ACTIVE_REAL_PLAYERS:
        return []
    count = random.randint(MIN_BOTS_PER_ROUND, MAX_BOTS_PER_ROUND)
    return [BotPlayer() for _ in range(count)]
