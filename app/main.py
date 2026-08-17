"""FastAPI main application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for creating DB tables on startup."""
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        # Allows startup during offline testing or when database is managed externally
        pass
    yield



app = FastAPI(
    title="LinkPlease Backend Service",
    description="Automated DM response service for comment triggers.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/")
def root():
    return {"message": "LinkPlease API is running"}
