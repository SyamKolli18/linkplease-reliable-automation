"""End-to-end integration and behavior tests for Part A."""

from unittest.mock import MagicMock
from app.clients.pseudogram import PseudoGramResponse
from app.workers.dm_worker import DMWorker


def make_payload(event_id, text, user_id, comment_id="cmt_888", post_id="post_999"):
    return {
        "event_id": event_id,
        "event_type": "comment.created",
        "sent_at": "2026-08-17T12:00:00.000Z",
        "data": {
            "comment_id": comment_id,
            "post_id": post_id,
            "text": text,
            "created_at": "2026-08-17T11:59:59.000Z",
            "from": {
                "user_id": user_id,
                "username": f"{user_id}_name"
            }
        }
    }


def test_e2e_full_flow(client, db_session):
    """Verify POST /rules -> POST /webhook -> Worker Execution -> GET /stats."""
    # 1. Create Rule
    rule_res = client.post("/rules", json={
        "keyword": "DISCOUNT",
        "dm_message": "Here is your 20% off code: SAVE20"
    })
    assert rule_res.status_code == 201

    # 2. Receive Webhook Event
    webhook_res = client.post("/webhook", json=make_payload("evt_e2e_001", "Is there any DISCOUNT available?", "usr_alpha", "cmt_888", "post_999"))
    assert webhook_res.status_code == 200
    assert webhook_res.json()["jobs_queued"] == 1

    # 3. Verify Stats initially shows queued=1
    stats1 = client.get("/stats").json()
    assert stats1["queued"] == 1
    assert stats1["sent"] == 0

    # 4. Run Worker to process job using db_session
    worker = DMWorker()
    worker.client.send_dm = MagicMock(return_value=PseudoGramResponse(status_code=202, dm_id="dm_e2e_1", dm_status="delivered"))
    
    claimed = worker.claim_jobs(db_session)
    assert len(claimed) == 1
    for job in claimed:
        worker.process_job(db_session, job)

    # 5. Verify API called with exact payload
    assert worker.client.send_dm.call_count == 1
    call_args = worker.client.send_dm.call_args[1]
    assert call_args["recipient_user_id"] == "usr_alpha"
    assert call_args["message"] == "Here is your 20% off code: SAVE20"
    assert call_args["comment_id"] == "cmt_888"

    # 6. Verify Stats updated to sent=1
    stats2 = client.get("/stats").json()
    assert stats2 == {
        "sent": 1,
        "failed": 0,
        "queued": 0,
        "duplicates_blocked": 0
    }


def test_e2e_duplicate_event_id_handling(client, db_session):
    """Verify sending same event_id twice does not create duplicate jobs."""
    client.post("/rules", json={"keyword": "PRICING", "dm_message": "See prices here"})

    payload = make_payload("evt_dup_999", "What is the PRICING?", "usr_beta", "cmt_1", "post_1")

    res1 = client.post("/webhook", json=payload)
    assert res1.status_code == 200
    assert res1.json()["jobs_queued"] == 1

    # Second arrival of same event_id
    res2 = client.post("/webhook", json=payload)
    assert res2.status_code == 200
    assert res2.json()["message"] == "Duplicate event ignored"

    # Worker runs and processes claimed jobs
    worker = DMWorker()
    worker.client.send_dm = MagicMock(return_value=PseudoGramResponse(status_code=202, dm_id="dm_dup_1", dm_status="delivered"))
    
    claimed = worker.claim_jobs(db_session)
    assert len(claimed) == 1
    for job in claimed:
        worker.process_job(db_session, job)

    assert worker.client.send_dm.call_count == 1
    stats = client.get("/stats").json()
    assert stats["sent"] == 1
    assert stats["queued"] == 0


def test_e2e_non_matching_comment_ignores(client, db_session):
    """Verify comments with no matching keywords do not queue jobs."""
    client.post("/rules", json={"keyword": "VIP", "dm_message": "Welcome to VIP"})

    res = client.post("/webhook", json=make_payload("evt_no_match", "Just saying hello!", "usr_gamma", "cmt_2", "post_1"))
    assert res.status_code == 200
    assert res.json()["jobs_queued"] == 0

    stats = client.get("/stats").json()
    assert stats == {"sent": 0, "failed": 0, "queued": 0, "duplicates_blocked": 0}


def test_e2e_same_user_same_rule_multiple_comments(client, db_session):
    """Verify same user commenting twice for same rule receives only 1 DM."""
    client.post("/rules", json={"keyword": "FREE", "dm_message": "Here is your free trial"})

    # First comment by user
    client.post("/webhook", json=make_payload("evt_user1_comment1", "Can I get a FREE trial?", "usr_delta", "cmt_10", "post_1"))

    # Second comment by same user matching same rule
    client.post("/webhook", json=make_payload("evt_user1_comment2", "I really need FREE access!", "usr_delta", "cmt_20", "post_2"))

    worker = DMWorker()
    worker.client.send_dm = MagicMock(return_value=PseudoGramResponse(status_code=202, dm_id="dm_delta_1", dm_status="delivered"))

    # Process all jobs
    jobs = worker.claim_jobs(db_session, limit=10)
    assert len(jobs) == 2
    for job in jobs:
        worker.process_job(db_session, job)

    # Verify external API called once for first comment
    assert worker.client.send_dm.call_count == 1

    # Verify stats
    stats = client.get("/stats").json()
    assert stats["sent"] == 1
    assert stats["duplicates_blocked"] == 1
    assert stats["queued"] == 0

