# LinkPlease Tech Intern Assignment - Part A

A reliable backend service built with Python 3.12, FastAPI, PostgreSQL, SQLAlchemy 2.0, and httpx to handle automated DM responses based on social media comment events.

---

## Technical Stack & Architecture

- **Web Application**: FastAPI (`POST /rules`, `POST /webhook`, `GET /stats`)
- **Database**: PostgreSQL (SQLAlchemy 2.0 ORM + Alembic)
- **Background Worker**: Independent Python process polling PostgreSQL with `SELECT ... FOR UPDATE SKIP LOCKED`
- **External Client**: `httpx` client for PseudoGram Mock API (`X-API-Key`, `Idempotency-Key`, `Retry-After` parsing)
- **Testing**: `pytest`

---

## Design Highlights & Reliability Guarantees

1. **Fast Webhook Persistence**: `POST /webhook` acknowledges requests in < 5s by persisting events and queuing jobs synchronously in PostgreSQL within a fast single transaction. No in-memory queues are used.
2. **Durable Queuing**: Web server restarts will never lose pending jobs (`dm_jobs` table).
3. **Concurrency-Safe Duplicate Prevention**: Unique constraint `UNIQUE(user_id, rule_id)` in PostgreSQL guarantees a user never receives duplicate DMs for the same rule, regardless of parallel comments or multiple worker instances.
4. **Safe Worker Claiming**: Workers use `SELECT ... FOR UPDATE SKIP LOCKED` to lock claimed jobs without worker blocking or duplicate processing.
5. **Robust Retry & Rate Limiting**:
   - `202 Accepted`: Success (`SENT`).
   - `429 Rate Limited`: Backs off using `Retry-After` header.
   - `500 Server Error`: Exponential backoff ($2^n \times 2\text{s} + \text{jitter}$), max 5 retries.
   - `400 Bad Request`: Permanent failure (`FAILED`), no retries.
   - Rate limit: Worker enforces conservative sliding window (<= 9 DMs per 60s).

---

## Setup & Running Locally

### 1. Environment Setup
Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```

Configure your PostgreSQL database connection string and PseudoGram API key:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/linkplease
PSEUDOGRAM_API_BASE_URL=https://pseudogram-api.onrender.com
PSEUDOGRAM_API_KEY=your_api_key_here
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run FastAPI Application
```bash
uvicorn app.main:app --reload --port 8000
```

### 4. Run Background Worker Process
In a separate terminal window:
```bash
python -m app.workers.dm_worker
```

### 5. Run Automated Tests
```bash
pytest -v
```

---

## Required API Contract

### POST /rules
**Request**:
```json
{
  "keyword": "PRICE",
  "dm_message": "Here is our current price list: https://example.com/pricing"
}
```
**Response (201 Created)**:
```json
{
  "rule_id": "c1f7b8d4-53a9-4b6e-821f-9df219b1b110",
  "keyword": "PRICE",
  "dm_message": "Here is our current price list: https://example.com/pricing"
}
```

### POST /webhook
**Request**:
```json
{
  "event_id": "evt_99812",
  "post_id": "post_100",
  "comment_id": "cmt_555",
  "user_id": "user_42",
  "text": "Can you send me the price?"
}
```
**Response (200 OK)**:
```json
{
  "status": "ok",
  "event_id": "evt_99812",
  "jobs_queued": 1
}
```

### GET /stats
**Response (200 OK)**:
```json
{
  "sent": 10,
  "failed": 1,
  "queued": 2,
  "duplicates_blocked": 3
}
```
