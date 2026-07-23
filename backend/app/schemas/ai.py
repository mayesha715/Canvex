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


class CanvasPosition(BaseModel):
    x: float
    y: float


class AIAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    # Optional base64 PNG of the canvas so Gemini can "see" it (vision model).
    snapshot_b64: str | None = None
    # Optional scene coords for where to drop the answer element.
    position: CanvasPosition | None = None

    @field_validator("question")
    @classmethod
    def _strip_question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Question cannot be blank")
        return normalized


class AIAskResponse(BaseModel):
    answer: str
    source: str  # "gemini" | "local" | "local-fallback"
    element: ElementRead
    interaction: AIInteractionRead
    latency_ms: int
