"""Rule request and response schemas."""

from pydantic import BaseModel, ConfigDict, Field


class RuleCreate(BaseModel):
    keyword: str = Field(..., min_length=1, description="Trigger keyword")
    dm_message: str = Field(..., min_length=1, description="Message to send via DM")


class RuleResponse(BaseModel):
    rule_id: str
    keyword: str
    dm_message: str

    model_config = ConfigDict(from_attributes=True)

