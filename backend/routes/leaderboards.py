from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query

from leaderboards import repository
from leaderboards.schemas import LeaderboardEntry, LeaderboardResponse

router = APIRouter(prefix="/leaderboards", tags=["Leaderboards"])


def _entries(rows: list[dict], value_key: str, extra_key: str | None = None) -> LeaderboardResponse:
    return LeaderboardResponse(entries=[
        LeaderboardEntry(
            user_id=r["user_id"], name=r["name"], value=r[value_key],
            extra=str(r[extra_key]) if extra_key else None,
        )
        for r in rows
    ])


@router.get("/richest", response_model=LeaderboardResponse)
def richest(limit: int = Query(10, ge=1, le=100)):
    return _entries(repository.richest_players(limit), "balance_cents")


@router.get("/biggest-win", response_model=LeaderboardResponse)
def biggest_win(limit: int = Query(10, ge=1, le=100)):
    return _entries(repository.biggest_wins(limit), "amount_cents", "game")


@router.get("/most-profit", response_model=LeaderboardResponse)
def most_profit(limit: int = Query(10, ge=1, le=100)):
    return _entries(repository.most_profit(limit), "profit_cents")


@router.get("/most-wagered", response_model=LeaderboardResponse)
def most_wagered(limit: int = Query(10, ge=1, le=100)):
    return _entries(repository.most_wagered(limit), "wagered_cents")


@router.get("/most-games-played", response_model=LeaderboardResponse)
def most_games_played(limit: int = Query(10, ge=1, le=100)):
    return _entries(repository.most_games_played(limit), "games_played")


@router.get("/biggest-crash-cashout", response_model=LeaderboardResponse)
def biggest_crash_cashout(limit: int = Query(10, ge=1, le=100)):
    return _entries(repository.biggest_crash_cashouts(limit), "payout_cents", "multiplier")


@router.get("/most-legendary-items", response_model=LeaderboardResponse)
def most_legendary_items(limit: int = Query(10, ge=1, le=100)):
    return _entries(repository.most_legendary_items(limit), "legendary_count")


@router.get("/daily-winners", response_model=LeaderboardResponse)
def daily_winners(limit: int = Query(10, ge=1, le=100)):
    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    return _entries(repository.most_profit(limit, since=since), "profit_cents")


@router.get("/weekly-winners", response_model=LeaderboardResponse)
def weekly_winners(limit: int = Query(10, ge=1, le=100)):
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    return _entries(repository.most_profit(limit, since=since), "profit_cents")


@router.get("/monthly-winners", response_model=LeaderboardResponse)
def monthly_winners(limit: int = Query(10, ge=1, le=100)):
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    return _entries(repository.most_profit(limit, since=since), "profit_cents")
