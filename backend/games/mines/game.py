"""Mines: pick tiles one at a time, each safe tile raises the multiplier,
hitting a mine busts the round. Mine locations are never sent to the
client until the round ends (either a bust reveals everything, or the
player cashes out and the reveal is purely informational at that point).
"""
import random

HOUSE_EDGE = 0.99
MIN_TOTAL_TILES = 4
MAX_TOTAL_TILES = 64
MIN_BET_CENTS = 100


class InvalidMinesConfigError(Exception):
    pass


def validate_config(total_tiles: int, mine_count: int, bet_amount_cents: int) -> None:
    if not (MIN_TOTAL_TILES <= total_tiles <= MAX_TOTAL_TILES):
        raise InvalidMinesConfigError(f"Board size must be between {MIN_TOTAL_TILES} and {MAX_TOTAL_TILES} tiles")
    if not (1 <= mine_count < total_tiles):
        raise InvalidMinesConfigError("Mine count must be at least 1 and less than the board size")
    if bet_amount_cents < MIN_BET_CENTS:
        raise InvalidMinesConfigError(f"Minimum bet is {MIN_BET_CENTS} cents")


def generate_mine_positions(total_tiles: int, mine_count: int) -> list[int]:
    return random.sample(range(total_tiles), mine_count)


def multiplier_for(total_tiles: int, mine_count: int, safe_reveals: int) -> float:
    """Fair (pre-house-edge) multiplier is 1/P(picking `safe_reveals` safe
    tiles in a row without replacement), scaled down by HOUSE_EDGE — the
    same hypergeometric-odds approach every mines-style game uses."""
    safe_tiles = total_tiles - mine_count
    multiplier = 1.0
    for i in range(safe_reveals):
        multiplier *= (total_tiles - i) / (safe_tiles - i)
    return round(multiplier * HOUSE_EDGE, 4)
