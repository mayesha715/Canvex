from __future__ import annotations

from uuid import UUID

from app.db.session import AsyncSessionLocal
from app.models.enums import AITriggerType
from app.services.ai import analyze_canvas_job, embed_element_text_job, redis_settings
from app.services.redis import get_redis


async def analyze_canvas(
    ctx: dict,
    *,
    page_id: str,
    trigger_element_id: str,
    trigger_type: str,
    snapshot_b64: str | None = None,
) -> None:
    async with AsyncSessionLocal() as db:
        await analyze_canvas_job(
            db,
            get_redis(),
            page_id=UUID(page_id),
            trigger_element_id=UUID(trigger_element_id),
            trigger_type=AITriggerType(trigger_type),
            snapshot_b64=snapshot_b64,
        )


async def embed_element_text(ctx: dict, *, element_id: str) -> None:
    async with AsyncSessionLocal() as db:
        await embed_element_text_job(db, element_id=UUID(element_id))


class WorkerSettings:
    functions = [analyze_canvas, embed_element_text]
    redis_settings = redis_settings()
    max_jobs = 4
    job_timeout = 30
