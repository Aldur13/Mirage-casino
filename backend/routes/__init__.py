from .account import router as account_router, dev_router as account_dev_router
from .auth import router as auth_router
from .blackjack import router as blackjack_router
from .crash import router as crash_router
from .mines import router as mines_router

__all__ = [
    "auth_router", "account_router", "account_dev_router", "crash_router", "mines_router",
    "blackjack_router",
]
