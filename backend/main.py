from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import settings
from database import close_driver, setup_constraints
from games.crash.round_manager import round_manager
from routes import (
    account_dev_router, account_router, auth_router, blackjack_router, crash_router, mines_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_constraints()
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
    allow_origins=["*"],
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

if settings.app_env != "production":
    app.include_router(account_dev_router, tags=["Dev"])


frontend_dir = Path(__file__).parent.parent / "frontend"


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    if not frontend_dir.exists():
        return {"error": "Frontend not found"}, 404

    file_path = frontend_dir / full_path
    if file_path.is_file() and file_path.is_relative_to(frontend_dir):
        return FileResponse(file_path)

    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    return {"error": "Not found"}, 404
