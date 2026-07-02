"""Hand evaluation and dealer AI. Dealer stands on all 17s (a common,
simple house rule — documented here since it changes the math slightly
from "hits on soft 17" variants)."""

BLACKJACK = 21
DEALER_STAND_AT = 17
MIN_BET_CENTS = 100


def hand_value(cards: list[dict]) -> tuple[int, bool]:
    """Returns (best_value, is_soft). is_soft means an Ace is counted as
    11 in that best value (relevant for display, not for comparison)."""
    total = 0
    aces = 0
    for card in cards:
        rank = card["rank"]
        if rank == "A":
            aces += 1
            total += 11
        elif rank in ("J", "Q", "K"):
            total += 10
        else:
            total += int(rank)

    is_soft = False
    while total > BLACKJACK and aces > 0:
        total -= 10
        aces -= 1
    if aces > 0 and total <= BLACKJACK:
        # At least one Ace is still counted as 11 in this total.
        is_soft = True

    return total, is_soft


def is_blackjack(cards: list[dict]) -> bool:
    return len(cards) == 2 and hand_value(cards)[0] == BLACKJACK


def is_bust(cards: list[dict]) -> bool:
    return hand_value(cards)[0] > BLACKJACK


def dealer_should_hit(dealer_cards: list[dict]) -> bool:
    value, _ = hand_value(dealer_cards)
    return value < DEALER_STAND_AT


def can_split(cards: list[dict]) -> bool:
    if len(cards) != 2:
        return False
    a, b = cards
    rank_value = lambda r: 10 if r in ("10", "J", "Q", "K") else r
    return rank_value(a["rank"]) == rank_value(b["rank"])


def settle_hand(player_cards: list[dict], dealer_cards: list[dict], bet_cents: int,
                 player_had_blackjack: bool) -> tuple[str, int]:
    """Returns (outcome, total_returned_cents). total_returned_cents is
    what comes back to the player for this hand — 0 for a loss (the
    wager was already taken when the bet was placed)."""
    if is_bust(player_cards):
        return "bust", 0

    dealer_value, _ = hand_value(dealer_cards)
    player_value, _ = hand_value(player_cards)
    dealer_blackjack = is_blackjack(dealer_cards)

    if player_had_blackjack:
        if dealer_blackjack:
            return "push", bet_cents
        return "blackjack", round(bet_cents * 2.5)

    if dealer_blackjack:
        return "loss", 0
    if is_bust(dealer_cards):
        return "win", bet_cents * 2
    if player_value > dealer_value:
        return "win", bet_cents * 2
    if player_value < dealer_value:
        return "loss", 0
    return "push", bet_cents
