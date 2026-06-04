from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import EventOperation


class ElementEventRead(BaseModel):
    id: UUID
    element_id: UUID
    page_id: UUID
    actor_id: UUID | None
    actor_display_name: str | None = None
    operation: EventOperation
    before_state: dict[str, Any] | None
    after_state: dict[str, Any] | None
    vector_clock: dict[str, int]
    occurred_at: datetime


class AuditPage(BaseModel):
    items: list[ElementEventRead]
    limit: int
    offset: int
    total: int


class RestoreRequest(BaseModel):
    target_timestamp: datetime


class RestoreSummary(BaseModel):
    restored_count: int


class SessionRead(BaseModel):
    id: UUID
    page_id: UUID
    started_at: datetime
    ended_at: datetime | None
