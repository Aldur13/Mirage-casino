"""Chicken Road: cross lanes one at a time, each survived lane raises the
multiplier, getting hit by a car busts the round. Which lanes are dangerous
is decided (and hidden from the client) for the whole road up front, exactly
like Mines' mine_positions — reveal only happens on bust or cashout.

Unlike Mines (odds drawn from a finite board without replacement), each lane
here is an independent coin flip at a fixed danger probability, so the
survival odds compound simply as (1 - danger_pct) ** lanes_crossed.
"""
import secrets

HOUSE_EDGE = 0.99
MAX_LANES = 25
MIN_BET_CENTS = 100

# Probability a given lane has a car in it, by difficulty.
DIFFICULTIES = {
    "easy": 0.15,
    "medium": 0.25,
    "hard": 0.40,
    "daredevil": 0.55,
}


class InvalidChickenConfigError(Exception):
    pass


def validate_config(difficulty: str, bet_amount_cents: int) -> None:
    if difficulty not in DIFFICULTIES:
        raise InvalidChickenConfigError(f"Difficulty must be one of {', '.join(DIFFICULTIES)}")
    if bet_amount_cents < MIN_BET_CENTS:
        raise InvalidChickenConfigError(f"Minimum bet is {MIN_BET_CENTS} cents")


def generate_lane_outcomes(difficulty: str) -> list[bool]:
    """One entry per lane for the whole road, True = car (danger). Uses
    secrets (not random) so outcomes can't be predicted/replayed."""
    danger_scaled = int(DIFFICULTIES[difficulty] * 10_000)
    return [secrets.randbelow(10_000) < danger_scaled for _ in range(MAX_LANES)]


def multiplier_for(difficulty: str, lanes_crossed: int) -> float:
    """Fair (pre-house-edge) multiplier is 1 / P(surviving `lanes_crossed`
    independent lanes in a row), scaled down by HOUSE_EDGE."""
    survival_pct = 1 - DIFFICULTIES[difficulty]
    fair_multiplier = (1 / survival_pct) ** lanes_crossed
    return round(fair_multiplier * HOUSE_EDGE, 4)
