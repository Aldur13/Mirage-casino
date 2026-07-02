"""Card representation and shoe handling.

A fresh, cryptographically-shuffled 6-deck shoe is dealt for every round
and discarded afterward (not persisted as a running shoe across rounds)
— simpler than a stateful shoe, and it removes any card-counting edge
from prior rounds since a new one is generated every time.
"""
import secrets

RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
SUITS = ["♠", "♥", "♦", "♣"]
DECK_COUNT = 6


def new_shoe() -> list[dict]:
    cards = [{"rank": rank, "suit": suit} for _ in range(DECK_COUNT) for rank in RANKS for suit in SUITS]
    shuffled = []
    while cards:
        idx = secrets.randbelow(len(cards))
        shuffled.append(cards.pop(idx))
    return shuffled


def draw(shoe: list[dict]) -> dict:
    return shoe.pop()
