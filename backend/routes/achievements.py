from fastapi import APIRouter, Depends

from achievements import service
from dependencies import get_current_user

router = APIRouter(prefix="/achievements", tags=["Achievements"])


@router.get("/me")
def my_achievements(current_user: dict = Depends(get_current_user)):
    return {"achievements": service.list_for_user(current_user["id"])}
