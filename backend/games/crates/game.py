import secrets

RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]
MIN_BET_CENTS = 1  # crate prices are set per-crate, not user-chosen


def pick_weighted_item(items: list[dict]) -> dict:
    """Server-side weighted random pick — the only place a crate's odds
    are ever resolved. Uses secrets (not random) so drops can't be
    predicted/replayed from a seeded PRNG."""
    total_weight = sum(item["drop_weight"] for item in items)
    roll = secrets.randbelow(total_weight)
    cumulative = 0
    for item in items:
        cumulative += item["drop_weight"]
        if roll < cumulative:
            return item
    return items[-1]  # unreachable in practice, guards float/rounding edge cases
