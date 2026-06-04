from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.models.channel import ChannelMember
from app.models.enums import MemberRole
from app.models.user import User
from app.schemas.whiteboard import ElementCreate, ElementRead, ElementUpdate
from app.services.audit import end_active_session, get_or_create_active_session, record_session_event
from app.services.elements import (
    assert_minimum_role,
    create_element_for_page,
    delete_element_state,
    get_channel_membership_for_user,
    get_element_or_404,
    get_page_or_404,
    update_element_state,
)
from app.services.redis import get_redis
from app.services.ws_manager import manager

router = APIRouter(tags=["websocket"])

LOCK_TTL_SECONDS = 10
CURSOR_TTL_SECONDS = 5


def lock_key(element_id: UUID) -> str:
    return f"lock:{element_id}"


def cursor_key(page_id: UUID) -> str:
    return f"cursor:{page_id}"


async def authenticate_websocket_user(db: AsyncSession, token: str | None) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing access token")
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from None

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return user


async def get_page_membership(db: AsyncSession, page_id: UUID, user_id: UUID) -> ChannelMember:
    page = await get_page_or_404(db, page_id)
    return await get_channel_membership_for_user(db, page.channel_id, user_id)


async def assert_no_foreign_lock(redis: Redis, element_id: UUID, user_id: UUID) -> None:
    locked_by = await redis.get(lock_key(element_id))
    if locked_by is not None and locked_by != str(user_id):
        raise HTTPException(status_code=423, detail="Element is locked by another user")


def element_payload(element: object) -> dict[str, Any]:
    return ElementRead.model_validate(element).model_dump(mode="json")


async def apply_element_operation(
    db: AsyncSession,
    redis: Redis,
    *,
    page_id: UUID,
    user_id: UUID,
    operation_payload: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    membership = await get_page_membership(db, page_id, user_id)
    assert_minimum_role(membership, MemberRole.EDITOR)

    operation = operation_payload.get("operation") or operation_payload.get("op")
    vector_clock = operation_payload.get("vector_clock") or {}

    if operation == "create":
        create_payload = ElementCreate.model_validate(
            {
                **dict(operation_payload.get("element") or operation_payload.get("data") or {}),
                "vector_clock": vector_clock,
            }
        )
        element = await create_element_for_page(db, page_id=page_id, payload=create_payload, actor_id=user_id)
        await db.commit()
        await db.refresh(element)
        return "create", element_payload(element)

    element_id = UUID(str(operation_payload.get("element_id") or operation_payload.get("id")))
    element = await get_element_or_404(db, element_id)
    if element.page_id != page_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Element not found on this page")
    await assert_no_foreign_lock(redis, element.id, user_id)

    if operation == "update":
        update_source = dict(operation_payload.get("element") or operation_payload.get("data") or {})
        for field in ("transform", "style", "content"):
            if field in operation_payload:
                update_source[field] = operation_payload[field]
        update_source["vector_clock"] = vector_clock
        update_payload = ElementUpdate.model_validate(update_source)
        await update_element_state(db, element=element, payload=update_payload, actor_id=user_id, role=membership.role)
        await db.commit()
        await db.refresh(element)
        return "update", element_payload(element)

    if operation == "delete":
        # TODO(phase-7): thread vector_clock into delete event logging once delete concurrency is modeled.
        await delete_element_state(db, element=element, actor_id=user_id, role=membership.role)
        await db.commit()
        return "delete", {"id": str(element.id), "page_id": str(page_id), "is_deleted": True}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported element operation")


async def send_error(websocket: WebSocket, exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        await websocket.send_json({"type": "element:error", "status": exc.status_code, "detail": exc.detail})
        return
    if isinstance(exc, (ValidationError, ValueError)):
        await websocket.send_json({"type": "element:error", "status": 422, "detail": str(exc)})
        return
    await websocket.send_json({"type": "element:error", "status": 500, "detail": "Element operation failed"})


async def try_send_error(websocket: WebSocket, exc: Exception) -> None:
    try:
        await send_error(websocket, exc)
    except RuntimeError:
        pass


async def record_ws_event(
    *,
    session_id: UUID,
    page_id: UUID,
    event_type: str,
    payload: dict[str, Any],
    actor_id: UUID,
) -> None:
    async with AsyncSessionLocal() as db:
        await record_session_event(
            db,
            session_id=session_id,
            page_id=page_id,
            event_type=event_type,
            payload=payload,
            actor_id=actor_id,
        )
        await db.commit()


@router.websocket("/ws/{page_id}")
async def canvas_ws(websocket: WebSocket, page_id: UUID) -> None:
    redis = get_redis()
    token = websocket.query_params.get("token")
    async with AsyncSessionLocal() as db:
        try:
            user = await authenticate_websocket_user(db, token)
            membership = await get_page_membership(db, page_id, user.id)
            assert_minimum_role(membership, MemberRole.VIEWER)
        except HTTPException:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    async with AsyncSessionLocal() as db:
        session = await get_or_create_active_session(db, page_id)
        await db.commit()
        session_id = session.id

    await manager.connect(websocket, page_id, user.id)
    await manager.broadcast(
        page_id,
        {"type": "presence:join", "payload": {"user_id": str(user.id), "display_name": user.display_name}},
        exclude=websocket,
    )

    try:
        while True:
            message = await websocket.receive_json()
            protocol = message.get("protocol", "canvas")
            if protocol != "canvas":
                await websocket.send_json({"type": "error", "status": 400, "detail": "Unsupported websocket protocol"})
                continue
            message_type = message.get("type")
            payload = dict(message.get("payload") or {})

            if message_type == "cursor:move":
                cursor_payload = {
                    "user_id": str(user.id),
                    "display_name": user.display_name,
                    "x": payload.get("x"),
                    "y": payload.get("y"),
                    "color": payload.get("color"),
                    "updated_at": datetime.now(UTC).isoformat(),
                }
                await redis.hset(cursor_key(page_id), str(user.id), json.dumps(cursor_payload))
                await redis.expire(cursor_key(page_id), CURSOR_TTL_SECONDS)
                await manager.broadcast(page_id, {"type": "cursor:move", "payload": cursor_payload}, exclude=websocket)

            elif message_type == "element:lock":
                try:
                    async with AsyncSessionLocal() as db:
                        membership = await get_page_membership(db, page_id, user.id)
                        assert_minimum_role(membership, MemberRole.EDITOR)
                        element_id = UUID(str(payload["element_id"]))
                        element = await get_element_or_404(db, element_id)
                        if element.page_id != page_id:
                            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Element not found on this page")
                        await redis.set(lock_key(element_id), str(user.id), ex=LOCK_TTL_SECONDS)
                        manager.remember_lock(websocket, element_id)
                    lock_payload = {"element_id": str(element_id), "locked_by": str(user.id), "ttl_s": LOCK_TTL_SECONDS}
                    await record_ws_event(
                        session_id=session_id,
                        page_id=page_id,
                        event_type="element:lock",
                        payload=lock_payload,
                        actor_id=user.id,
                    )
                    await websocket.send_json({"type": "element:lock:ack", "payload": lock_payload})
                    await manager.broadcast(page_id, {"type": "element:lock", "payload": lock_payload}, exclude=websocket)
                except Exception as exc:
                    await try_send_error(websocket, exc)

            elif message_type == "element:op":
                try:
                    async with AsyncSessionLocal() as db:
                        operation, element_data = await apply_element_operation(
                            db,
                            redis,
                            page_id=page_id,
                            user_id=user.id,
                            operation_payload=payload,
                        )
                    event = {"type": "element:op", "operation": operation, "payload": element_data}
                    ack = {"type": "element:ack", "operation": operation, "payload": element_data}
                    if payload.get("client_operation_id") is not None:
                        ack["client_operation_id"] = payload["client_operation_id"]
                    await record_ws_event(
                        session_id=session_id,
                        page_id=page_id,
                        event_type="element:op",
                        payload={"operation": operation, "payload": element_data},
                        actor_id=user.id,
                    )
                    await websocket.send_json(ack)
                    await manager.broadcast(page_id, event, exclude=websocket)
                except Exception as exc:
                    await try_send_error(websocket, exc)

            else:
                await websocket.send_json({"type": "error", "status": 400, "detail": "Unsupported message type"})

    except WebSocketDisconnect:
        pass
    finally:
        released_locks = manager.disconnect(websocket, page_id)
        await redis.hdel(cursor_key(page_id), str(user.id))
        for element_id in released_locks:
            if await redis.get(lock_key(element_id)) == str(user.id):
                await redis.delete(lock_key(element_id))
                unlock_payload = {"element_id": str(element_id), "unlocked_by": str(user.id)}
                await record_ws_event(
                    session_id=session_id,
                    page_id=page_id,
                    event_type="element:unlock",
                    payload=unlock_payload,
                    actor_id=user.id,
                )
                await manager.broadcast(
                    page_id,
                    {"type": "element:unlock", "payload": unlock_payload},
                    exclude=websocket,
                )
        await manager.broadcast(page_id, {"type": "presence:leave", "payload": {"user_id": str(user.id)}}, exclude=websocket)
        if page_id not in manager.rooms:
            async with AsyncSessionLocal() as db:
                await end_active_session(db, page_id)
                await db.commit()


@router.get("/pages/{page_id}/presence")
async def get_presence(
    page_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    membership = await get_page_membership(db, page_id, current_user.id)
    assert_minimum_role(membership, MemberRole.VIEWER)
    count = await get_redis().hlen(cursor_key(page_id))
    return {"count": count}
