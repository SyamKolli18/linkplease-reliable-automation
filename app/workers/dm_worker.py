"""Background worker process for reading pending DM jobs from PostgreSQL and executing them."""

import logging
import random
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.clients.pseudogram import PseudoGramClient
from app.config import settings
from app.database import SessionLocal
from app.models.delivery import UserRuleDelivery
from app.models.dm_job import DMJob, JobStatus

logger = logging.getLogger(__name__)


class DMWorker:
    """Worker process managing DM queue execution, retries, and rate limiting."""

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self.client = PseudoGramClient()

    def check_rate_limit(self, db: Session) -> bool:
        """Check if sending another DM would exceed 10 requests per 60 seconds.
        
        Returns True if safe to send, False if rate limited.
        """
        sixty_secs_ago = datetime.now(timezone.utc) - timedelta(seconds=60)
        recent_sent_count = (
            db.query(DMJob)
            .filter(
                DMJob.status == JobStatus.SENT.value,
                DMJob.updated_at >= sixty_secs_ago,
            )
            .count()
        )
        # Conservative threshold: max 9 requests per 60 seconds
        return recent_sent_count < 9

    def claim_jobs(self, db: Session, limit: int = 5) -> list[DMJob]:
        """Safely claim pending jobs using SELECT ... FOR UPDATE SKIP LOCKED."""
        now = datetime.now(timezone.utc)
        
        try:
            query = (
                db.query(DMJob)
                .filter(
                    DMJob.status.in_([JobStatus.QUEUED.value, JobStatus.ACCEPTED.value]),
                    DMJob.next_retry_at <= now,
                )
                .order_by(DMJob.created_at.asc())
                .limit(limit)
            )

            # Use FOR UPDATE SKIP LOCKED on PostgreSQL (ignored gracefully on SQLite during testing)
            try:
                query = query.with_for_update(skip_locked=True)
            except (DBAPIError, NotImplementedError):
                pass

            jobs = query.all()
            if not jobs:
                return []

            # Transition claimed jobs to PROCESSING
            job_ids = [j.id for j in jobs]
            for job in jobs:
                job.status = JobStatus.PROCESSING.value
                job.updated_at = now
            db.commit()

            # Re-query jobs to ensure they are bound to fresh session context if needed
            return db.query(DMJob).filter(DMJob.id.in_(job_ids)).all()

        except Exception as e:
            db.rollback()
            logger.error(f"Error claiming jobs: {e}")
            return []

    def process_job(self, db: Session, job: DMJob):
        """Process a single claimed DMJob."""
        logger.info(f"Processing job {job.id} for user {job.user_id}, rule {job.rule_id}")
        now = datetime.now(timezone.utc)

        # If job already has a dm_id, poll delivery status via GET /v1/dm/{dm_id}
        if job.dm_id:
            response = self.client.get_dm_status(job.dm_id)
            if response.status_code == 200:
                if response.dm_status == "delivered":
                    job.status = JobStatus.SENT.value
                    job.updated_at = now
                    job.last_error = None
                    db.commit()
                    logger.info(f"DM {job.dm_id} for job {job.id} confirmed delivered.")
                elif response.dm_status == "failed":
                    job.status = JobStatus.FAILED.value
                    job.updated_at = now
                    job.last_error = "PseudoGram DM delivery failed."
                    db.commit()
                    logger.error(f"DM {job.dm_id} for job {job.id} failed on PseudoGram API.")
                else:
                    # Still queued on mock server, check again shortly
                    job.status = JobStatus.ACCEPTED.value
                    job.next_retry_at = now + timedelta(seconds=1)
                    job.updated_at = now
                    db.commit()
            else:
                # Transient error checking status, retry checking later
                job.status = JobStatus.ACCEPTED.value
                job.next_retry_at = now + timedelta(seconds=2)
                job.updated_at = now
                db.commit()
            return

        delivery = None

        # Step 1: Check duplicate delivery per user and rule
        existing_delivery = (
            db.query(UserRuleDelivery)
            .filter_by(user_id=job.user_id, rule_id=job.rule_id)
            .first()
        )
        if existing_delivery:
            logger.info(f"User {job.user_id} already received DM for rule {job.rule_id}. Blocking duplicate.")
            job.status = JobStatus.DUPLICATE_BLOCKED.value
            job.updated_at = now
            db.commit()
            return

        # Step 2: Optimistically attempt delivery insertion in a savepoint to catch concurrent worker races
        savepoint = db.begin_nested()
        delivery = UserRuleDelivery(
            user_id=job.user_id,
            rule_id=job.rule_id,
            job_id=job.id,
        )
        db.add(delivery)
        try:
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
            logger.info(f"Race condition caught: User {job.user_id} delivery already exists for rule {job.rule_id}.")
            job.status = JobStatus.DUPLICATE_BLOCKED.value
            job.updated_at = now
            db.commit()
            return

        # Step 3: Call PseudoGram API
        idempotency_key = f"job_{job.id}"
        response = self.client.send_dm(
            recipient_user_id=job.user_id,
            message=job.dm_message,
            comment_id=job.comment_id,
            idempotency_key=idempotency_key,
        )

        def _remove_delivery_if_present():
            nonlocal delivery
            if delivery is not None and delivery in db:
                db.delete(delivery)

        # Step 4: Handle response status codes
        if response.status_code == 202:
            # Success: DM queued/accepted by PseudoGram
            job.dm_id = response.dm_id
            if response.dm_status == "delivered":
                job.status = JobStatus.SENT.value
            elif response.dm_status == "failed":
                job.status = JobStatus.FAILED.value
            else:
                job.status = JobStatus.ACCEPTED.value
                job.next_retry_at = now + timedelta(seconds=1)

            job.updated_at = now
            job.last_error = None
            db.commit()
            logger.info(f"Successfully sent DM request for job {job.id}, dm_id={job.dm_id}")

        elif response.status_code == 429:
            # Rate limited: rollback delivery lock so it can retry later
            _remove_delivery_if_present()
            job.retry_count += 1
            retry_seconds = response.retry_after or 60
            job.next_retry_at = now + timedelta(seconds=retry_seconds)
            job.status = JobStatus.QUEUED.value
            job.last_error = f"429 Rate Limited. Retry after {retry_seconds}s"
            job.updated_at = now
            db.commit()
            logger.warning(f"Job {job.id} rate limited (429). Retrying in {retry_seconds}s")

        elif response.status_code == 500 or response.status_code is None:
            # Server error / network failure: apply exponential backoff
            _remove_delivery_if_present()
            job.retry_count += 1
            if job.retry_count >= job.max_retries:
                job.status = JobStatus.FAILED.value
                job.last_error = f"Max retries reached. Last error: {response.error_message}"
                logger.error(f"Job {job.id} failed permanently after {job.retry_count} retries.")
            else:
                backoff_seconds = (2 ** job.retry_count) * 2 + random.uniform(0, 1)
                job.next_retry_at = now + timedelta(seconds=backoff_seconds)
                job.status = JobStatus.QUEUED.value
                job.last_error = f"500 Server Error: {response.error_message}"
                logger.warning(f"Job {job.id} transient error. Retrying in {backoff_seconds:.1f}s")
            job.updated_at = now
            db.commit()

        elif response.status_code == 400:
            # Client error: Invalid request, do NOT retry
            _remove_delivery_if_present()
            job.status = JobStatus.FAILED.value
            job.last_error = f"400 Bad Request: {response.error_message}"
            job.updated_at = now
            db.commit()
            logger.error(f"Job {job.id} failed with 400 Bad Request. Will not retry.")

        else:
            # Unhandled status code
            _remove_delivery_if_present()
            job.retry_count += 1
            if job.retry_count >= job.max_retries:
                job.status = JobStatus.FAILED.value
            else:
                job.status = JobStatus.QUEUED.value
                job.next_retry_at = now + timedelta(seconds=30)
            job.last_error = f"HTTP {response.status_code}: {response.error_message}"
            job.updated_at = now
            db.commit()

    def run_once(self):
        """Run a single iteration of claiming and processing jobs."""
        db = SessionLocal()
        try:
            if not self.check_rate_limit(db):
                logger.info("Rate limit threshold reached (10 DMs/60s). Sleeping worker.")
                time.sleep(5)
                return

            jobs = self.claim_jobs(db, limit=5)
            for job in jobs:
                self.process_job(db, job)
        finally:
            db.close()

    def run(self):
        """Main loop for running background worker process continuously."""
        logger.info("Starting DM Worker process...")
        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Unhandled error in worker loop: {e}")
            time.sleep(self.poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    worker = DMWorker(poll_interval=settings.WORKER_POLL_INTERVAL)
    worker.run()
