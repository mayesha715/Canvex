from __future__ import annotations
# ruff: noqa: E402

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.audit import ElementEvent
from app.models.channel import Channel, ChannelMember
from app.models.element import WhiteboardElement
from app.models.enums import ElementType, EventOperation, MemberRole
from app.models.page import WhiteboardPage
from app.models.user import User


def element_state(element: WhiteboardElement) -> dict:
    return {
        "id": str(element.id),
        "page_id": str(element.page_id),
        "type": element.type.value,
        "transform": element.transform,
        "style": element.style,
        "content": element.content,
        "is_deleted": element.is_deleted,
    }


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == "owner@canvex.local"))
        if existing:
            print("Seed data already exists.")
            return

        owner = User(
            email="owner@canvex.local",
            display_name="Canvex Owner",
            password_hash="$2b$12$development.seed.password.hash",
        )
        teammate = User(
            email="editor@canvex.local",
            display_name="Canvex Editor",
            password_hash="$2b$12$development.seed.password.hash",
        )
        db.add_all([owner, teammate])
        await db.flush()

        channel = Channel(
            name="Design Lab",
            description="Seed channel for Phase 1 schema testing.",
            owner_id=owner.id,
        )
        db.add(channel)
        await db.flush()

        db.add_all(
            [
                ChannelMember(channel_id=channel.id, user_id=owner.id, role=MemberRole.OWNER),
                ChannelMember(channel_id=channel.id, user_id=teammate.id, role=MemberRole.EDITOR),
            ]
        )

        pages = [
            WhiteboardPage(channel_id=channel.id, title="Discovery", order_index=0, created_by=owner.id),
            WhiteboardPage(channel_id=channel.id, title="Sketches", order_index=1, created_by=owner.id),
            WhiteboardPage(channel_id=channel.id, title="Review", order_index=2, created_by=teammate.id),
        ]
        db.add_all(pages)
        await db.flush()

        element_types = [
            ElementType.STROKE,
            ElementType.RECT,
            ElementType.ELLIPSE,
            ElementType.TEXT,
            ElementType.MATH,
            ElementType.STICKY,
            ElementType.ARROW,
            ElementType.LINK,
        ]

        elements: list[WhiteboardElement] = []
        for index in range(20):
            page = pages[index % len(pages)]
            kind = element_types[index % len(element_types)]
            element = WhiteboardElement(
                id=uuid4(),
                page_id=page.id,
                created_by=owner.id if index % 2 == 0 else teammate.id,
                type=kind,
                transform={
                    "x": 80 + (index * 37) % 700,
                    "y": 70 + (index * 53) % 420,
                    "scaleX": 1,
                    "scaleY": 1,
                    "rotation": 0,
                },
                style={
                    "stroke": "#111827",
                    "fill": "#f8fafc" if kind in {ElementType.RECT, ElementType.ELLIPSE, ElementType.STICKY} else "transparent",
                    "strokeWidth": 2,
                },
                content={
                    "text": f"Seed element {index + 1}",
                    "points": [[0, 0], [24, 12], [48, 0]] if kind == ElementType.STROKE else [],
                },
            )
            db.add(element)
            elements.append(element)

        await db.flush()

        for element in elements:
            event = ElementEvent(
                element_id=element.id,
                page_id=element.page_id,
                actor_id=element.created_by,
                operation=EventOperation.CREATE,
                before_state=None,
                after_state=element_state(element),
                vector_clock={"seed": 1},
            )
            db.add(event)
            await db.flush()
            element.last_event = event.id

        await db.commit()
        print("Seeded 2 users, 1 channel, 3 pages, 20 elements, and 20 events.")


if __name__ == "__main__":
    asyncio.run(seed())
