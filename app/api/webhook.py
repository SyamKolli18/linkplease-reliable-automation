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

    # Extract user_id safely from data.from if available
    user_id = payload.data.from_user.user_id if payload.data.from_user else None

    # 2. Persist event
    event = Event(
        id=payload.event_id,
        event_type=payload.event_type,
        post_id=payload.data.post_id,
        comment_id=payload.data.comment_id,
        user_id=user_id,
        text=payload.data.text,
    )
    db.add(event)

    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.info(f"Duplicate event conflict caught: {payload.event_id}.")
        return {"status": "ok", "message": "Duplicate event ignored"}

    # 3. If comment.deleted or missing text/user_id, save event and return HTTP 200 without queuing jobs
    if payload.event_type == "comment.deleted" or not payload.data.text or not user_id:
        db.commit()
        return {
            "status": "ok",
            "event_id": payload.event_id,
            "jobs_queued": 0,
            "message": "Event processed (no rule matching required)",
        }

    # 4. Match active keyword rules
    matched_rules = match_rules(payload.data.text, db)
    
    # 5. Queue DM jobs for matched rules synchronously inside transaction
    now = datetime.now(timezone.utc)
    for rule in matched_rules:
        job = DMJob(
            event_id=event.id,
            rule_id=rule.id,
            user_id=user_id,
            comment_id=payload.data.comment_id,
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
