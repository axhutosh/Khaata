from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..auth import current_user
from .. import insights as ins

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/overview")
def overview(period: str = "month", user: User = Depends(current_user), db: Session = Depends(get_db)):
    if period not in ("day", "month", "year"):
        period = "month"
    return ins.overview(db, user.id, period)


@router.get("/recurring")
def recurring(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ins.recurring(db, user.id)
