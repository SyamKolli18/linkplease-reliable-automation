"""Tests for GET /stats endpoint."""

from datetime import datetime, timezone

from app.models.dm_job import DMJob, JobStatus
from app.models.event import Event
from app.models.rule import Rule


def test_stats_counts(client, db_session):
    rule = Rule(id="r1", keyword="KEY", dm_message="Msg")
    event = Event(id="e1", post_id="p1", comment_id="c1", user_id="u1", text="KEY")
    db_session.add_all([rule, event])
    db_session.commit()

    now = datetime.now(timezone.utc)
    job_sent = DMJob(id="j1", event_id="e1", rule_id="r1", user_id="u1", comment_id="c1", dm_message="M", status=JobStatus.SENT.value, next_retry_at=now)
    job_failed = DMJob(id="j2", event_id="e1", rule_id="r1", user_id="u1", comment_id="c1", dm_message="M", status=JobStatus.FAILED.value, next_retry_at=now)
    job_queued = DMJob(id="j3", event_id="e1", rule_id="r1", user_id="u1", comment_id="c1", dm_message="M", status=JobStatus.QUEUED.value, next_retry_at=now)
    job_dup = DMJob(id="j4", event_id="e1", rule_id="r1", user_id="u1", comment_id="c1", dm_message="M", status=JobStatus.DUPLICATE_BLOCKED.value, next_retry_at=now)

    db_session.add_all([job_sent, job_failed, job_queued, job_dup])
    db_session.commit()

    res = client.get("/stats")
    assert res.status_code == 200
    data = res.json()

    assert data == {
        "sent": 1,
        "failed": 1,
        "queued": 1,
        "duplicates_blocked": 1,
    }
