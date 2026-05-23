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


async def main() -> None:
    email = f"phase2_{int(time.time())}@canvex.local"
    password = "correct-horse-42"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.post(
            "/auth/register",
            json={"email": email, "display_name": "Phase Two", "password": password},
        )
        require_status("register", response.status_code, 201, response.text)
        register_body = response.json()
        access_token = register_body["access_token"]
        register_refresh_token = register_body["refresh_token"]

        response = await client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
        require_status("me", response.status_code, 200, response.text)
        if response.json()["email"] != email:
            raise AssertionError("me: returned the wrong user")

        response = await client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
        require_status("invalid_access_token", response.status_code, 401, response.text)

        response = await client.post("/auth/token", data={"username": email, "password": "wrong-password"})
        require_status("bad_login", response.status_code, 401, response.text)

        response = await client.post("/auth/token", data={"username": email, "password": password})
        require_status("login", response.status_code, 200, response.text)
        login_refresh_token = response.json()["refresh_token"]

        response = await client.post("/auth/refresh", json={"refresh_token": register_refresh_token})
        require_status("refresh", response.status_code, 200, response.text)

        response = await client.post("/auth/refresh", json={"refresh_token": register_refresh_token})
        require_status("reuse_old_refresh", response.status_code, 401, response.text)

        response = await client.post("/auth/logout", json={"refresh_token": login_refresh_token})
        require_status("logout", response.status_code, 204, response.text)

    await engine.dispose()
    print("Phase 2 auth flow passed")


if __name__ == "__main__":
    asyncio.run(main())
