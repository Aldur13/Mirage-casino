from typing import Optional
from pydantic import BaseModel


class StatisticsResponse(BaseModel):
    games_played: int
    games_won: int
    games_lost: int
    total_wagered_cents: int
    total_profit_cents: int
    biggest_win_cents: int
    biggest_loss_cents: int
    favorite_game: Optional[str] = None

    crash_games_played: int
    crash_games_won: int
    crash_highest_multiplier: Optional[float] = None

    mines_games_played: int
    mines_cashouts: int

    blackjack_hands_played: int
    blackjack_win_rate_pct: Optional[float] = None

    crates_opened: int
    legendary_items_obtained: int
