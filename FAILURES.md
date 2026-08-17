# Failure Modes & System Resilience

This document outlines potential failure scenarios in the LinkPlease backend, how the system handles each scenario gracefully, and why architectural decisions were made.

---

## 1. Web Process Crash / Restart Mid-Request
- **Scenario**: The web server receives a `POST /webhook` request and crashes before responding or immediately after.
- **Handling**: Webhook events are saved to the `events` table and pending jobs are inserted into `dm_jobs` in a single synchronous database transaction **before** the web server returns HTTP 200. No pending work is stored solely in in-memory queues (like FastAPI `BackgroundTasks`).
- **Resilience**: If the web process restarts, all pending jobs remain safely persisted in `dm_jobs` with status `QUEUED` and will be processed by the background worker.

## 2. Duplicate Webhook Deliveries (At-Least-Once Delivery)
- **Scenario**: PseudoGram API sends the exact same `event_id` multiple times due to network retries.
- **Handling**: The `events` table primary key is `id` (`event_id`). On webhook receipt, the web server executes:
  `INSERT INTO events (...) VALUES (...) ON CONFLICT (id) DO NOTHING;`
- **Resilience**: If 0 rows are inserted, the event was already processed. The webhook endpoint returns HTTP 200 immediately without creating duplicate `dm_jobs`.

## 3. Multiple Comments Matching the Same Rule by the Same User
- **Scenario**: User `usr_001` posts 5 comments containing "PRICE". Rule `rule_price` exists.
- **Handling**: Requirement 4 & 5 mandate that a user receives at most 1 DM per rule ever.
- **Resilience**: The database table `user_rule_deliveries` has a unique constraint `UNIQUE(user_id, rule_id)`. When the worker attempts to process a job, it executes:
  `INSERT INTO user_rule_deliveries (user_id, rule_id, job_id) VALUES (...) ON CONFLICT (user_id, rule_id) DO NOTHING;`
- If 0 rows are inserted, the job is marked `DUPLICATE_BLOCKED` and no external HTTP DM request is made. The unique DB constraint prevents concurrency race conditions across multiple workers.

## 4. Concurrent Workers Processing Jobs
- **Scenario**: Multiple worker instances run simultaneously to scale throughput.
- **Handling**: Workers fetch pending jobs using PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED`.
- **Resilience**: PostgreSQL locks claimed rows for the duration of the claiming transaction and skips locked rows for other workers. This eliminates race conditions and ensures zero lock contention.

## 5. PseudoGram API 429 Rate Limiting
- **Scenario**: PseudoGram returns HTTP 429 with `Retry-After: 60`.
- **Handling**: The worker parses `Retry-After` header (defaulting to 60 seconds if absent), sets `dm_jobs.next_retry_at = NOW() + delay`, keeps status as `QUEUED`, and increments `retry_count`.
- **Resilience**: The worker also maintains a conservative sliding-window rate check (<= 9 DMs per 60s) to prevent exceeding PseudoGram's 10 DM / 60s limit intentionally.

## 6. PseudoGram API 500 Internal Error
- **Scenario**: PseudoGram API experiences temporary outage or server errors.
- **Handling**: Exponential backoff is applied ($\text{delay} = 2^{\text{retry\_count}} \times 2\text{s} + \text{jitter}$). Job `next_retry_at` is updated. After 5 retries, status becomes `FAILED` and `last_error` is logged.

## 7. PseudoGram API 400 Bad Request
- **Scenario**: Webhook data contains invalid recipient ID or invalid payload.
- **Handling**: Immediate permanent failure (`status = 'FAILED'`). No retries are performed for 400 client errors to avoid endless retry loops.
