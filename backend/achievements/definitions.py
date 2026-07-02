"""The achievement catalog. Adding a new achievement is just adding an
entry here — service.py evaluates every definition's check() against a
context dict built from the player's current stats, so nothing else
needs to change for new achievements that reuse existing context fields.
"""

ACHIEVEMENTS = [
    {"id": "first_bet", "name": "First Bet", "description": "Place your first wager.",
     "check": lambda c: c["games_played"] >= 1},
    {"id": "first_win", "name": "First Win", "description": "Win a game for the first time.",
     "check": lambda c: c["games_won"] >= 1},
    {"id": "lucky", "name": "Lucky", "description": "Win 10 games.",
     "check": lambda c: c["games_won"] >= 10},
    {"id": "millionaire", "name": "Millionaire", "description": "Reach a bank balance of 1,000,000.00.",
     "check": lambda c: c["balance_cents"] >= 100_000_000},
    {"id": "high_roller", "name": "High Roller", "description": "Wager 100.00 or more in a single bet.",
     "check": lambda c: c["biggest_single_wager_cents"] >= 10_000},
    {"id": "blackjack_master", "name": "Blackjack Master", "description": "Win 25 Blackjack hands.",
     "check": lambda c: c["blackjack_wins"] >= 25},
    {"id": "mine_expert", "name": "Mine Expert", "description": "Cash out 25 Mines rounds.",
     "check": lambda c: c["mines_cashouts"] >= 25},
    {"id": "crash_addict", "name": "Crash Addict", "description": "Play 50 Crash rounds.",
     "check": lambda c: c["crash_games_played"] >= 50},
    {"id": "legendary_pull", "name": "Legendary Pull", "description": "Obtain a legendary crate item.",
     "check": lambda c: c["legendary_items_obtained"] >= 1},
    {"id": "hundred_games", "name": "100 Games", "description": "Play 100 games total.",
     "check": lambda c: c["games_played"] >= 100},
    {"id": "thousand_games", "name": "1000 Games", "description": "Play 1000 games total.",
     "check": lambda c: c["games_played"] >= 1000},
    {"id": "huge_profit", "name": "Huge Profit", "description": "Reach 10,000.00 in total profit.",
     "check": lambda c: c["total_profit_cents"] >= 1_000_000},
]

BY_ID = {a["id"]: a for a in ACHIEVEMENTS}
