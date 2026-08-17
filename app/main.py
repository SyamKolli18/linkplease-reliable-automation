"""FastAPI main application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for application startup/shutdown."""
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
