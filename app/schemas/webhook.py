"""Webhook event request schema."""

from pydantic import BaseModel, Field


class WebhookEvent(BaseModel):
    event_id: str = Field(..., description="Unique event ID")
    post_id: str = Field(..., description="ID of post")
    comment_id: str = Field(..., description="ID of comment")
    user_id: str = Field(..., description="ID of user who commented")
    text: str = Field(..., description="Text content of comment")
