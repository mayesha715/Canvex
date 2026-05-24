from __future__ import annotations
# ruff: noqa: E402

import asyncio
import sys
import time
from pathlib import Path
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.db.session import AsyncSessionLocal, engine
from app.main import app
from app.models.audit import ElementEvent
from app.models.element import ElementPermission
from app.models.enums import EventOperation, MemberRole


def require_status(label: str, actual: int, expected: int, body: object) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected}, got {actual}: {body}")


async def register(client: AsyncClient, email: str, display_name: str) -> dict[str, str]:
    response = await client.post(
        "/auth/register",
        json={"email": email, "display_name": display_name, "password": "correct-horse-42"},
    )
    require_status(f"register {email}", response.status_code, 201, response.text)
    body = response.json()
    return {"access": body["access_token"], "user_id": body["user"]["id"]}


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def load_element_events(element_id: str) -> list[ElementEvent]:
    async with AsyncSessionLocal() as db:
        events = await db.scalars(
            select(ElementEvent)
            .where(ElementEvent.element_id == UUID(element_id))
            .order_by(ElementEvent.occurred_at.asc())
        )
        return list(events.all())


async def block_editor_edits(element_id: str) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            ElementPermission(
                element_id=UUID(element_id),
                role=MemberRole.EDITOR,
                can_read=True,
                can_edit=False,
                can_delete=False,
            )
        )
        await db.commit()


async def main() -> None:
    stamp = int(time.time())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        owner = await register(client, f"phase4_owner_{stamp}@canvex.local", "Phase Four Owner")
        editor = await register(client, f"phase4_editor_{stamp}@canvex.local", "Phase Four Editor")
        viewer = await register(client, f"phase4_viewer_{stamp}@canvex.local", "Phase Four Viewer")

        response = await client.post(
            "/channels",
            json={"name": f"Phase 4 Channel {stamp}", "description": "Whiteboard verification"},
            headers=auth(owner["access"]),
        )
        require_status("create channel", response.status_code, 201, response.text)
        channel_id = response.json()["id"]

        response = await client.post(
            f"/channels/{channel_id}/invites",
            json={"role_on_join": "editor", "max_uses": 1},
            headers=auth(owner["access"]),
        )
        require_status("create editor invite", response.status_code, 201, response.text)
        editor_invite = response.json()["code"]

        response = await client.post(
            f"/channels/{channel_id}/invites",
            json={"role_on_join": "viewer", "max_uses": 1},
            headers=auth(owner["access"]),
        )
        require_status("create viewer invite", response.status_code, 201, response.text)
        viewer_invite = response.json()["code"]

        response = await client.post(f"/invites/{editor_invite}/accept", headers=auth(editor["access"]))
        require_status("editor accept invite", response.status_code, 200, response.text)
        response = await client.post(f"/invites/{viewer_invite}/accept", headers=auth(viewer["access"]))
        require_status("viewer accept invite", response.status_code, 200, response.text)

        response = await client.post(
            f"/channels/{channel_id}/pages",
            json={"title": "Main canvas"},
            headers=auth(owner["access"]),
        )
        require_status("owner create first page", response.status_code, 201, response.text)
        first_page = response.json()
        first_page_id = first_page["id"]
        if first_page["order_index"] != 0:
            raise AssertionError("first page order_index should be 0")

        response = await client.post(
            f"/channels/{channel_id}/pages",
            json={"title": "Second canvas"},
            headers=auth(owner["access"]),
        )
        require_status("owner create second page", response.status_code, 201, response.text)
        second_page_id = response.json()["id"]

        response = await client.post(
            f"/channels/{channel_id}/pages",
            json={"title": "Viewer should fail"},
            headers=auth(viewer["access"]),
        )
        require_status("viewer create page forbidden", response.status_code, 403, response.text)

        response = await client.patch(
            f"/pages/{second_page_id}",
            json={"order_index": 0},
            headers=auth(owner["access"]),
        )
        require_status("reorder second page", response.status_code, 200, response.text)
        if response.json()["order_index"] != 0:
            raise AssertionError("second page should move to order_index 0")

        response = await client.get(f"/channels/{channel_id}/pages", headers=auth(viewer["access"]))
        require_status("viewer list pages", response.status_code, 200, response.text)
        pages = response.json()
        if [page["id"] for page in pages] != [second_page_id, first_page_id]:
            raise AssertionError("page reorder did not update list order")

        response = await client.post(
            f"/pages/{first_page_id}/elements",
            json={
                "type": "text",
                "transform": {"x": 10, "y": 20, "scaleX": 1, "scaleY": 1, "rotation": 0},
                "style": {"stroke": "#111111", "fill": "transparent", "strokeWidth": 2},
                "content": {"text": "hello phase four"},
                "vector_clock": {"owner-client": 1},
            },
            headers=auth(owner["access"]),
        )
        require_status("owner create element", response.status_code, 201, response.text)
        element = response.json()
        element_id = element["id"]

        events = await load_element_events(element_id)
        if len(events) != 1 or events[0].operation != EventOperation.CREATE:
            raise AssertionError("create element should write one create event")
        if events[0].before_state is not None or events[0].after_state["content"]["text"] != "hello phase four":
            raise AssertionError("create event state is incorrect")
        if events[0].vector_clock != {"owner-client": 1}:
            raise AssertionError("create event vector clock is incorrect")

        response = await client.get(
            f"/pages/{first_page_id}/elements",
            params={"type": "text", "search": "phase four"},
            headers=auth(viewer["access"]),
        )
        require_status("viewer filter elements", response.status_code, 200, response.text)
        if [item["id"] for item in response.json()] != [element_id]:
            raise AssertionError("type/search filter did not return the created element")

        response = await client.patch(
            f"/elements/{element_id}",
            json={"content": {"text": "hello updated"}, "vector_clock": {"owner-client": 2}},
            headers=auth(viewer["access"]),
        )
        require_status("viewer update element forbidden", response.status_code, 403, response.text)

        response = await client.patch(
            f"/elements/{element_id}",
            json={"content": {"text": "hello updated"}, "vector_clock": {"owner-client": 2}},
            headers=auth(owner["access"]),
        )
        require_status("owner update element", response.status_code, 200, response.text)

        response = await client.patch(
            f"/elements/{element_id}",
            json={"content": None},
            headers=auth(owner["access"]),
        )
        require_status("null update rejected as empty", response.status_code, 400, response.text)

        events = await load_element_events(element_id)
        if len(events) != 2 or events[1].operation != EventOperation.UPDATE:
            raise AssertionError("update element should append one update event")
        if events[1].before_state["content"]["text"] != "hello phase four":
            raise AssertionError("update event before_state is incorrect")
        if events[1].after_state["content"]["text"] != "hello updated":
            raise AssertionError("update event after_state is incorrect")

        await block_editor_edits(element_id)
        response = await client.patch(
            f"/elements/{element_id}",
            json={"content": {"text": "editor should fail"}},
            headers=auth(editor["access"]),
        )
        require_status("element permission blocks editor", response.status_code, 403, response.text)

        response = await client.delete(f"/elements/{element_id}", headers=auth(owner["access"]))
        require_status("owner delete element", response.status_code, 204, response.text)

        response = await client.get(f"/pages/{first_page_id}/elements", headers=auth(owner["access"]))
        require_status("deleted element omitted", response.status_code, 200, response.text)
        if response.json():
            raise AssertionError("soft-deleted element should not appear in element list")

        events = await load_element_events(element_id)
        if len(events) != 3 or events[2].operation != EventOperation.DELETE:
            raise AssertionError("delete element should append one delete event")
        if not events[2].after_state["is_deleted"]:
            raise AssertionError("delete event after_state should mark element deleted")

    await engine.dispose()
    print("Phase 4 whiteboard flow passed")


if __name__ == "__main__":
    asyncio.run(main())
