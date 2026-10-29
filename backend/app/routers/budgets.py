from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User, Budget
from ..auth import current_user
from .. import insights as ins

router = APIRouter(prefix="/budgets", tags=["budgets"])


class BudgetIn(BaseModel):
    category: str
    monthly_limit: float


@router.get("")
def list_budgets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ins.budget_status(db, user.id)


@router.put("")
def upsert_budget(body: BudgetIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    b = db.query(Budget).filter(Budget.user_id == user.id, Budget.category == body.category).first()
    if b:
        b.monthly_limit = body.monthly_limit
    else:
        db.add(Budget(user_id=user.id, category=body.category, monthly_limit=body.monthly_limit))
    db.commit()
    return {"ok": True}
