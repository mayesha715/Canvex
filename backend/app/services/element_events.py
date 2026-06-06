from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import ElementEvent
from app.models.element import WhiteboardElement
from app.models.enums import EventOperation


JsonState = dict[str, Any]


def element_state(element: WhiteboardElement) -> JsonState:
    return {
        "id": str(element.id),
        "page_id": str(element.page_id),
        "created_by": str(element.created_by) if element.created_by else None,
        "type": element.type.value,
        "transform": deepcopy(element.transform),
        "style": deepcopy(element.style),
        "content": deepcopy(element.content),
        "locked_by": str(element.locked_by) if element.locked_by else None,
        "is_deleted": element.is_deleted,
    }


async def log_element_event(
    db: AsyncSession,
    *,
    element: WhiteboardElement,
    actor_id: UUID | None,
    operation: EventOperation,
    before_state: JsonState | None,
    after_state: JsonState | None,
    vector_clock: dict[str, int] | None = None,
) -> ElementEvent:
    event = ElementEvent(
        element_id=element.id,
        page_id=element.page_id,
        actor_id=actor_id,
        operation=operation,
        before_state=before_state,
        after_state=after_state,
        vector_clock=dict(vector_clock or {}),
    )
    db.add(event)
    await db.flush()
    element.last_event = event.id
    return event
