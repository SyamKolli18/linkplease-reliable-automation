"""Webhook event request schema matching official PseudoGram API format."""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserData(BaseModel):
    user_id: str = Field(..., description="ID of user who commented")
    username: Optional[str] = Field(None, description="Username of user")


class EventData(BaseModel):
    comment_id: str = Field(..., description="ID of comment")
    post_id: Optional[str] = Field(None, description="ID of post")
    text: Optional[str] = Field(None, description="Text content of comment")
    created_at: Optional[str] = Field(None, description="Creation timestamp of comment")
    from_user: Optional[UserData] = Field(None, alias="from", description="User who posted comment")

    model_config = ConfigDict(populate_by_name=True)


class WebhookEvent(BaseModel):
    event_id: str = Field(..., description="Unique event ID")
    event_type: str = Field("comment.created", description="Type of event e.g. comment.created, comment.deleted")
    sent_at: Optional[str] = Field(None, description="Event dispatch timestamp")
    data: EventData = Field(..., description="Event payload data")

