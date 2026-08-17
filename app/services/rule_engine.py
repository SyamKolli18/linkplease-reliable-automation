"""Rule engine service for keyword matching."""

from sqlalchemy.orm import Session

from app.models.rule import Rule


def match_rules(text: str, db: Session) -> list[Rule]:
    """Find all active rules matching the comment text case-insensitively.
    
    Keyword matching must be case-insensitive and match anywhere in the comment text.
    """
    if not text:
        return []

    rules = db.query(Rule).all()
    text_lower = text.lower()
    
    matched = []
    for rule in rules:
        if rule.keyword and rule.keyword.lower() in text_lower:
            matched.append(rule)
            
    return matched
