from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AITriggerType
from app.schemas.whiteboard import ElementRead


class AIInteractionRead(BaseModel):
    id: UUID
    page_id: UUID
    trigger_element_id: UUID | None
    trigger_type: AITriggerType
    canvas_snapshot_url: str | None
    prompt_sent: str
    response_json: dict[str, Any] | None
    response_element_id: UUID | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    status: str
    error_message: str | None
    created_at: datetime


class AIFeedbackCreate(BaseModel):
    is_correct: bool
    correction_text: str | None = Field(default=None, max_length=2000)

    @field_validator("correction_text")
    @classmethod
    def normalize_correction(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        return normalized or None


class AIFeedbackRead(BaseModel):
    id: UUID
    interaction_id: UUID
    user_id: UUID
    is_correct: bool
    correction_text: str | None
    created_at: datetime


class AISearchResult(BaseModel):
    element: ElementRead
    similarity: float
