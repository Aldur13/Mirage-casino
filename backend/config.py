from pathlib import Path

from pydantic_settings import BaseSettings

# Resolved relative to this file rather than the process's cwd, so it
# works whether uvicorn is launched from backend/ (`cd backend && ...`,
# mirage-bank's convention) or from the repo root (e.g. the dev preview
# tooling, which passes --app-dir backend without chdir-ing there).
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Same Neo4j Aura instance and JWT secret as Mirage Bank — this is what
    # makes the two apps recognize the same users and balances.
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_database: str = "neo4j"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    cors_origins: str = (
        "http://localhost:8914,"
        "http://127.0.0.1:8914,"
        "https://mirage-casino.vercel.app"
    )

    app_env: str = "development"

    model_config = {
        "env_file": str(_ENV_FILE),
        "extra": "ignore",
    }


settings = Settings()
