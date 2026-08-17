"""Stats API route handler."""

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dm_job import DMJob, JobStatus
from app.schemas.stats import StatsResponse

router = APIRouter(tags=["Stats"])


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Return stats on DM jobs sent, failed, queued, and duplicates blocked."""
    stats_query = db.query(
        func.coalesce(
            func.sum(case((DMJob.status == JobStatus.SENT.value, 1), else_=0)), 0
        ).label("sent"),
        func.coalesce(
            func.sum(case((DMJob.status == JobStatus.FAILED.value, 1), else_=0)), 0
        ).label("failed"),
        func.coalesce(
            func.sum(
                case(
                    (
                        DMJob.status.in_(
                            [JobStatus.QUEUED.value, JobStatus.PROCESSING.value]
                        ),
                        1,
                    ),
                    else_=0,
                )
            ),
            0,
        ).label("queued"),
        func.coalesce(
            func.sum(
                case((DMJob.status == JobStatus.DUPLICATE_BLOCKED.value, 1), else_=0)
            ),
            0,
        ).label("duplicates_blocked"),
    ).first()

    return StatsResponse(
        sent=int(stats_query.sent) if stats_query else 0,
        failed=int(stats_query.failed) if stats_query else 0,
        queued=int(stats_query.queued) if stats_query else 0,
        duplicates_blocked=int(stats_query.duplicates_blocked) if stats_query else 0,
    )
