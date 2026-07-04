from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from config import settings
from database import close_driver, setup_constraints
from games.crash.round_manager import round_manager
from games.crates.repository import seed_default_crates
from routes import (
    account_dev_router, account_router, achievements_router, auth_router, blackjack_router,
    chicken_router, crash_router, crates_router, leaderboards_router, mines_router, statistics_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_constraints()
    seed_default_crates()
    round_manager.start()
    yield
    round_manager.stop()
    close_driver()


app = FastAPI(
    title="Mirage Casino API",
    description="Mirage Casino — Phase 1 (shared auth + ledger foundation)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/auth", tags=["Auth"])
app.include_router(account_router, tags=["Account"])
app.include_router(crash_router)
app.include_router(mines_router)
app.include_router(blackjack_router)
app.include_router(crates_router)
app.include_router(chicken_router)
app.include_router(statistics_router)
app.include_router(leaderboards_router)
app.include_router(achievements_router)

if settings.app_env != "production":
    app.include_router(account_dev_router, tags=["Dev"])


frontend_dir = Path(__file__).parent / "frontend"


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if not frontend_dir.exists():
        return JSONResponse({"error": "Frontend not found"}, status_code=404)

    # Resolve before the containment check: is_relative_to() is purely
    # lexical and does not collapse "..", so an unresolved path could
    # escape the frontend dir. Resolving first blocks path traversal.
    base = frontend_dir.resolve()
    file_path = (base / full_path).resolve()

    if file_path.is_file() and file_path.is_relative_to(base):
        return FileResponse(file_path)

    index_path = base / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)

    return JSONResponse({"error": "Not found"}, status_code=404)
