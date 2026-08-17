"""Rules API route handlers."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.rule import Rule
from app.schemas.rule import RuleCreate, RuleResponse

router = APIRouter(tags=["Rules"])


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)):
    """Create a keyword rule for automated DM responses."""
    rule = Rule(
        keyword=payload.keyword,
        dm_message=payload.dm_message,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)

    return RuleResponse(
        rule_id=rule.id,
        keyword=rule.keyword,
        dm_message=rule.dm_message,
    )
