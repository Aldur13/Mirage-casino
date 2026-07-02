from .account import router as account_router, dev_router as account_dev_router
from .achievements import router as achievements_router
from .auth import router as auth_router
from .blackjack import router as blackjack_router
from .crash import router as crash_router
from .crates import router as crates_router
from .leaderboards import router as leaderboards_router
from .mines import router as mines_router
from .statistics import router as statistics_router

__all__ = [
    "auth_router", "account_router", "account_dev_router", "crash_router", "mines_router",
    "blackjack_router", "crates_router", "statistics_router", "leaderboards_router",
    "achievements_router",
]
