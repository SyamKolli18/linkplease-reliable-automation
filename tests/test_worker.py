"""Tests for background worker execution, status handling, retries, and duplicate prevention."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.clients.pseudogram import PseudoGramResponse
from app.models.dm_job import DMJob, JobStatus
from app.models.event import Event
from app.models.rule import Rule
from app.workers.dm_worker import DMWorker


def setup_job(db_session, event_id="evt_w1", user_id="usr_001", rule_keyword="PRICE"):
    rule = Rule(id=f"rule_{rule_keyword}", keyword=rule_keyword, dm_message="Price is $10")
    event = Event(id=event_id, post_id="p1", comment_id="c1", user_id=user_id, text=rule_keyword)
    job = DMJob(
        id=f"job_{event_id}",
        event_id=event.id,
        rule_id=rule.id,
        user_id=user_id,
        comment_id=event.comment_id,
        dm_message=rule.dm_message,
        status=JobStatus.QUEUED.value,
        next_retry_at=datetime.now(timezone.utc),
    )
    db_session.add_all([rule, event, job])
    db_session.commit()
    return job


def test_worker_process_202_accepted(db_session):
    job = setup_job(db_session, event_id="evt_202", user_id="u1")
    worker = DMWorker()
    worker.client.send_dm = MagicMock(return_value=PseudoGramResponse(status_code=202))

    worker.process_job(db_session, job)
    
    db_session.refresh(job)
    assert job.status == JobStatus.SENT.value
    assert job.last_error is None


def test_worker_duplicate_prevention_same_user_same_rule(db_session):
    # First job for user u1 and rule PRICE
    job1 = setup_job(db_session, event_id="evt_d1", user_id="u1", rule_keyword="PRICE")
    
    # Second job for same user u1 and same rule PRICE
    event2 = Event(id="evt_d2", post_id="p1", comment_id="c2", user_id="u1", text="PRICE again")
    job2 = DMJob(
        id="job_evt_d2",
        event_id=event2.id,
        rule_id=job1.rule_id,
        user_id="u1",
        comment_id="c2",
        dm_message="Price is $10",
        status=JobStatus.QUEUED.value,
        next_retry_at=datetime.now(timezone.utc),
    )
    db_session.add_all([event2, job2])
    db_session.commit()

    worker = DMWorker()
    worker.client.send_dm = MagicMock(return_value=PseudoGramResponse(status_code=202))

    # Process first job -> should succeed (SENT)
    worker.process_job(db_session, job1)
    db_session.refresh(job1)
    assert job1.status == JobStatus.SENT.value

    # Process second job -> should be blocked as DUPLICATE_BLOCKED
    worker.process_job(db_session, job2)
    db_session.refresh(job2)
    assert job2.status == JobStatus.DUPLICATE_BLOCKED.value


def test_worker_handles_429_rate_limit(db_session):
    job = setup_job(db_session, event_id="evt_429", user_id="u2")
    worker = DMWorker()
    worker.client.send_dm = MagicMock(
        return_value=PseudoGramResponse(status_code=429, retry_after=45)
    )

    worker.process_job(db_session, job)

    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED.value
    assert job.retry_count == 1
    assert "429 Rate Limited" in job.last_error


def test_worker_handles_500_server_error(db_session):
    job = setup_job(db_session, event_id="evt_500", user_id="u3")
    worker = DMWorker()
    worker.client.send_dm = MagicMock(
        return_value=PseudoGramResponse(status_code=500, error_message="Internal Error")
    )

    worker.process_job(db_session, job)

    db_session.refresh(job)
    assert job.status == JobStatus.QUEUED.value
    assert job.retry_count == 1
    assert "500 Server Error" in job.last_error


def test_worker_handles_400_bad_request_no_retry(db_session):
    job = setup_job(db_session, event_id="evt_400", user_id="u4")
    worker = DMWorker()
    worker.client.send_dm = MagicMock(
        return_value=PseudoGramResponse(status_code=400, error_message="Invalid recipient")
    )

    worker.process_job(db_session, job)

    db_session.refresh(job)
    assert job.status == JobStatus.FAILED.value
    assert "400 Bad Request" in job.last_error
