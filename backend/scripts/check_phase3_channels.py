from __future__ import annotations
# ruff: noqa: E402

import asyncio
import sys
import time
from pathlib import Path

from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.db.session import engine
from app.main import app


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


async def main() -> None:
    stamp = int(time.time())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        owner = await register(client, f"phase3_owner_{stamp}@canvex.local", "Phase Three Owner")
        editor = await register(client, f"phase3_editor_{stamp}@canvex.local", "Phase Three Editor")
        viewer = await register(client, f"phase3_viewer_{stamp}@canvex.local", "Phase Three Viewer")
        leaver = await register(client, f"phase3_leaver_{stamp}@canvex.local", "Phase Three Leaver")
        outsider = await register(client, f"phase3_outsider_{stamp}@canvex.local", "Phase Three Outsider")

        response = await client.post(
            "/channels",
            json={"name": f"Phase 3 Channel {stamp}", "description": "RBAC verification"},
            headers=auth(owner["access"]),
        )
        require_status("create channel", response.status_code, 201, response.text)
        channel = response.json()
        channel_id = channel["id"]
        if channel["owner_id"] != owner["user_id"]:
            raise AssertionError("create channel: owner_id mismatch")

        response = await client.get("/channels", headers=auth(owner["access"]))
        require_status("owner list channels", response.status_code, 200, response.text)
        if not any(item["id"] == channel_id and item["role"] == "owner" for item in response.json()):
            raise AssertionError("owner list channels: created channel missing")

        response = await client.post(
            f"/channels/{channel_id}/invites",
            json={"role_on_join": "editor", "max_uses": 3},
            headers=auth(owner["access"]),
        )
        require_status("owner create editor invite", response.status_code, 201, response.text)
        editor_invite = response.json()["code"]

        response = await client.post(f"/invites/{editor_invite}/accept", headers=auth(editor["access"]))
        require_status("editor accept invite", response.status_code, 200, response.text)
        if response.json()["role"] != "editor":
            raise AssertionError("editor accept invite: wrong role")

        response = await client.post(f"/invites/{editor_invite}/accept", headers=auth(leaver["access"]))
        require_status("second editor accept invite", response.status_code, 200, response.text)
        if response.json()["role"] != "editor":
            raise AssertionError("second editor accept invite: wrong role")

        response = await client.delete(
            f"/channels/{channel_id}/members/{leaver['user_id']}",
            headers=auth(leaver["access"]),
        )
        require_status("editor self remove", response.status_code, 204, response.text)

        response = await client.get(f"/channels/{channel_id}", headers=auth(leaver["access"]))
        require_status("self removed editor forbidden", response.status_code, 403, response.text)

        response = await client.post(f"/invites/{editor_invite}/accept", headers=auth(editor["access"]))
        require_status("duplicate accept", response.status_code, 409, response.text)

        response = await client.patch(
            f"/channels/{channel_id}",
            json={"description": "editor should not edit channel settings"},
            headers=auth(editor["access"]),
        )
        require_status("editor patch forbidden", response.status_code, 403, response.text)

        response = await client.put(
            f"/channels/{channel_id}/members/{editor['user_id']}",
            json={"role": "admin"},
            headers=auth(editor["access"]),
        )
        require_status("editor self promote forbidden", response.status_code, 403, response.text)

        response = await client.put(
            f"/channels/{channel_id}/members/{editor['user_id']}",
            json={"role": "admin"},
            headers=auth(owner["access"]),
        )
        require_status("owner promote editor", response.status_code, 200, response.text)
        if response.json()["role"] != "admin":
            raise AssertionError("owner promote editor: wrong role")

        response = await client.patch(
            f"/channels/{channel_id}",
            json={"description": "updated by admin"},
            headers=auth(editor["access"]),
        )
        require_status("admin patch channel", response.status_code, 200, response.text)

        response = await client.post(
            f"/channels/{channel_id}/invites",
            json={"role_on_join": "viewer", "max_uses": 1},
            headers=auth(editor["access"]),
        )
        require_status("admin create viewer invite", response.status_code, 201, response.text)
        viewer_invite = response.json()["code"]

        response = await client.post(f"/invites/{viewer_invite}/accept", headers=auth(viewer["access"]))
        require_status("viewer accept invite", response.status_code, 200, response.text)
        if response.json()["role"] != "viewer":
            raise AssertionError("viewer accept invite: wrong role")

        response = await client.post(f"/invites/{viewer_invite}/accept", headers=auth(outsider["access"]))
        require_status("max uses exhausted", response.status_code, 410, response.text)

        response = await client.post(
            f"/channels/{channel_id}/invites",
            json={"role_on_join": "owner"},
            headers=auth(owner["access"]),
        )
        require_status("owner invite rejected", response.status_code, 422, response.text)

        response = await client.get(f"/channels/{channel_id}", headers=auth(viewer["access"]))
        require_status("viewer get channel", response.status_code, 200, response.text)

        response = await client.delete(
            f"/channels/{channel_id}/members/{viewer['user_id']}",
            headers=auth(editor["access"]),
        )
        require_status("admin remove viewer", response.status_code, 204, response.text)

        response = await client.get(f"/channels/{channel_id}", headers=auth(viewer["access"]))
        require_status("removed viewer forbidden", response.status_code, 403, response.text)

        response = await client.delete(
            f"/channels/{channel_id}/members/{editor['user_id']}",
            headers=auth(editor["access"]),
        )
        require_status("admin self remove", response.status_code, 204, response.text)

        response = await client.get(f"/channels/{channel_id}", headers=auth(editor["access"]))
        require_status("self removed admin forbidden", response.status_code, 403, response.text)

    await engine.dispose()
    print("Phase 3 channel flow passed")


if __name__ == "__main__":
    asyncio.run(main())
