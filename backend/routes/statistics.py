from collections import Counter

from fastapi import APIRouter, Depends

from dependencies import get_current_user
from stats import repository
from stats.schemas import StatisticsResponse

router = APIRouter(prefix="/statistics", tags=["Statistics"])


@router.get("/me", response_model=StatisticsResponse)
def my_statistics(current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    rounds = repository.get_round_ledger_rows(user_id)

    total_wagered = sum(r["wagered"] for r in rounds)
    total_paid = sum(r["paid"] for r in rounds)
    biggest_loss = max((r["wagered"] - r["paid"] for r in rounds if r["wagered"] > r["paid"]), default=0)
    games_won = sum(1 for r in rounds if r["paid"] > r["wagered"])
    games_lost = sum(1 for r in rounds if r["paid"] < r["wagered"])

    wagered_by_game = Counter()
    for r in rounds:
        wagered_by_game[r["game"]] += r["wagered"]
    favorite_game = wagered_by_game.most_common(1)[0][0] if wagered_by_game else None

    crash = repository.get_crash_stats(user_id)
    mines = repository.get_mines_stats(user_id)
    crates = repository.get_crates_stats(user_id)

    bj_hands = repository.get_blackjack_hands(user_id)
    bj_decided = [h for h in bj_hands if h["outcome"] not in (None, "push")]
    bj_wins = [h for h in bj_decided if h["outcome"] in ("win", "blackjack")]
    win_rate = round(len(bj_wins) / len(bj_decided) * 100, 2) if bj_decided else None

    return StatisticsResponse(
        games_played=len(rounds),
        games_won=games_won,
        games_lost=games_lost,
        total_wagered_cents=total_wagered,
        total_profit_cents=total_paid - total_wagered,
        biggest_win_cents=repository.get_biggest_win_cents(user_id),
        biggest_loss_cents=biggest_loss,
        favorite_game=favorite_game,
        crash_games_played=crash["played"],
        crash_games_won=crash["won"],
        crash_highest_multiplier=crash["highest_multiplier"],
        mines_games_played=mines["played"],
        mines_cashouts=mines["cashouts"],
        blackjack_hands_played=len(bj_hands),
        blackjack_win_rate_pct=win_rate,
        crates_opened=crates["opened"],
        legendary_items_obtained=crates["legendary"],
    )
