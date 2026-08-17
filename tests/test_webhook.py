"""Tests for Webhook ingestion endpoint."""

from app.models.dm_job import DMJob
from app.models.event import Event


def test_webhook_creates_event_and_job(client, db_session):
    # Setup rule
    rule_res = client.post("/rules", json={"keyword": "DISCOUNT", "dm_message": "Use code SAVE10"})
    assert rule_res.status_code == 201

    payload = {
        "event_id": "evt_001",
        "post_id": "post_100",
        "comment_id": "cmt_200",
        "user_id": "usr_777",
        "text": "Can I get a discount?"
    }

    response = client.post("/webhook", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["jobs_queued"] == 1

    # Verify event stored in DB
    event = db_session.query(Event).filter_by(id="evt_001").first()
    assert event is not None
    assert event.user_id == "usr_777"

    # Verify job queued in DB
    jobs = db_session.query(DMJob).filter_by(event_id="evt_001").all()
    assert len(jobs) == 1
    assert jobs[0].user_id == "usr_777"
    assert jobs[0].status == "QUEUED"


def test_duplicate_webhook_event_ignored(client, db_session):
    client.post("/rules", json={"keyword": "DISCOUNT", "dm_message": "Use code SAVE10"})

    payload = {
        "event_id": "evt_002",
        "post_id": "post_100",
        "comment_id": "cmt_200",
        "user_id": "usr_777",
        "text": "Any discount?"
    }

    # Send first time
    res1 = client.post("/webhook", json=payload)
    assert res1.status_code == 200

    # Send second time (duplicate event_id)
    res2 = client.post("/webhook", json=payload)
    assert res2.status_code == 200
    assert res2.json()["message"] == "Duplicate event ignored"

    # Verify only 1 job exists in total
    jobs = db_session.query(DMJob).filter_by(event_id="evt_002").all()
    assert len(jobs) == 1
