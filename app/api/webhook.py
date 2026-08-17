"""Webhook API route handler."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dm_job import DMJob, JobStatus
from app.models.event import Event
from app.schemas.webhook import WebhookEvent
from app.services.rule_engine import match_rules

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Webhook"])


@router.post("/webhook", status_code=status.HTTP_200_OK)
def handle_webhook(payload: WebhookEvent, db: Session = Depends(get_db)):
    """Receives comment events from PseudoGram API.
    
    Persists incoming event and queues matching jobs in PostgreSQL,
    returning HTTP 200 quickly within < 5 seconds.
    """
    # 1. Deduplicate event by event_id
    existing_event = db.query(Event).filter(Event.id == payload.event_id).first()
    if existing_event:
        logger.info(f"Duplicate event received: {payload.event_id}. Skipping processing.")
        return {"status": "ok", "message": "Duplicate event ignored"}

    # 2. Persist event
    event = Event(
        id=payload.event_id,
        post_id=payload.post_id,
        comment_id=payload.comment_id,
        user_id=payload.user_id,
        text=payload.text,
    )
    db.add(event)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info(f"Duplicate event conflict caught: {payload.event_id}.")
        return {"status": "ok", "message": "Duplicate event ignored"}

    # 3. Match active keyword rules
    matched_rules = match_rules(payload.text, db)
    
    # 4. Queue DM jobs for matched rules synchronously inside transaction
    now = datetime.now(timezone.utc)
    for rule in matched_rules:
        job = DMJob(
            event_id=event.id,
            rule_id=rule.id,
            user_id=payload.user_id,
            comment_id=payload.comment_id,
            dm_message=rule.dm_message,
            status=JobStatus.QUEUED.value,
            next_retry_at=now,
        )
        db.add(job)

    db.commit()

    return {
        "status": "ok",
        "event_id": payload.event_id,
        "jobs_queued": len(matched_rules),
    }
