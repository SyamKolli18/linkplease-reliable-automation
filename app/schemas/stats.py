"""Stats response schema strictly following required API contract."""

from pydantic import BaseModel


class StatsResponse(BaseModel):
    sent: int
    failed: int
    queued: int
    duplicates_blocked: int
