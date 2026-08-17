"""Tests for Webhook ingestion endpoint."""

from app.models.dm_job import DMJob
from app.models.event import Event


def make_nested_payload(event_id="evt_001", text="Can I get a discount?", user_id="usr_777", event_type="comment.created"):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "sent_at": "2026-08-17T12:00:00.000Z",
        "data": {
            "comment_id": "cmt_200",
            "post_id": "post_100",
            "text": text,
            "created_at": "2026-08-17T11:59:59.000Z",
            "from": {
                "user_id": user_id,
                "username": "test_user"
            }
        }
    }


def test_webhook_creates_event_and_job(client, db_session):
    # Setup rule
    rule_res = client.post("/rules", json={"keyword": "DISCOUNT", "dm_message": "Use code SAVE10"})
    assert rule_res.status_code == 201

    payload = make_nested_payload("evt_001", "Can I get a discount?", "usr_777")

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

    payload = make_nested_payload("evt_002", "Any discount?", "usr_777")

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


def test_comment_deleted_event_ignored(client, db_session):
    client.post("/rules", json={"keyword": "DISCOUNT", "dm_message": "Use code SAVE10"})

    payload = {
        "event_id": "evt_deleted_001",
        "event_type": "comment.deleted",
        "sent_at": "2026-08-17T12:00:00.000Z",
        "data": {
            "comment_id": "cmt_deleted_200"
        }
    }

    res = client.post("/webhook", json=payload)
    assert res.status_code == 200
    assert res.json()["jobs_queued"] == 0

    # Event stored
    event = db_session.query(Event).filter_by(id="evt_deleted_001").first()
    assert event is not None
    assert event.event_type == "comment.deleted"

