"""API router package."""

from fastapi import APIRouter

from app.api.rules import router as rules_router
from app.api.stats import router as stats_router
from app.api.webhook import router as webhook_router

api_router = APIRouter()
api_router.include_router(rules_router)
api_router.include_router(webhook_router)
api_router.include_router(stats_router)
