from typing import Optional
from pydantic import BaseModel


class LeaderboardEntry(BaseModel):
    user_id: str
    name: str
    value: float
    extra: Optional[str] = None


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
