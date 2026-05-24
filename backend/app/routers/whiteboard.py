from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.middleware.rbac import ROLE_RANK, require_channel_role
from app.models.channel import ChannelMember
from app.models.element import ElementPermission, WhiteboardElement
from app.models.enums import ElementType, EventOperation, MemberRole
from app.models.page import WhiteboardPage
from app.models.user import User
from app.schemas.whiteboard import ElementCreate, ElementRead, ElementUpdate, PageCreate, PageRead, PageUpdate
from app.services.element_events import element_state, log_element_event

router = APIRouter(tags=["whiteboard"])

PageAccess = tuple[WhiteboardPage, ChannelMember]
ElementAccess = tuple[WhiteboardElement, WhiteboardPage, ChannelMember]


async def get_page_or_404(db: AsyncSession, page_id: UUID) -> WhiteboardPage:
    page = await db.get(WhiteboardPage, page_id)
    if page is None or page.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return page


async def get_element_or_404(db: AsyncSession, element_id: UUID) -> WhiteboardElement:
    element = await db.get(WhiteboardElement, element_id)
    if element is None or element.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Element not found")
    return element


async def get_channel_membership_for_user(db: AsyncSession, channel_id: UUID, user_id: UUID) -> ChannelMember:
    membership = await db.scalar(
        select(ChannelMember).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == user_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this channel")
    return membership


def require_page_role(minimum_role: MemberRole) -> Callable[..., Coroutine[Any, Any, PageAccess]]:
    async def dependency(
        page_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> PageAccess:
        page = await get_page_or_404(db, page_id)
        membership = await get_channel_membership_for_user(db, page.channel_id, current_user.id)
        if ROLE_RANK[membership.role] < ROLE_RANK[minimum_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient channel role")
        return page, membership

    return dependency


def require_element_role(minimum_role: MemberRole) -> Callable[..., Coroutine[Any, Any, ElementAccess]]:
    async def dependency(
        element_id: UUID,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> ElementAccess:
        element = await get_element_or_404(db, element_id)
        page = await get_page_or_404(db, element.page_id)
        membership = await get_channel_membership_for_user(db, page.channel_id, current_user.id)
        if ROLE_RANK[membership.role] < ROLE_RANK[minimum_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient channel role")
        return element, page, membership

    return dependency


async def assert_can_mutate_element(
    db: AsyncSession,
    element: WhiteboardElement,
    role: MemberRole,
    *,
    deleting: bool = False,
) -> None:
    permission = await db.get(ElementPermission, {"element_id": element.id, "role": role})
    if permission is None:
        return
    if not permission.can_edit:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Element is locked for your role")
    if deleting and not permission.can_delete:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Element cannot be deleted by your role")


@router.post("/channels/{channel_id}/pages", response_model=PageRead, status_code=status.HTTP_201_CREATED)
async def create_page(
    channel_id: UUID,
    payload: PageCreate,
    _: ChannelMember = Depends(require_channel_role(MemberRole.EDITOR)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WhiteboardPage:
    max_order = await db.scalar(
        select(func.coalesce(func.max(WhiteboardPage.order_index), -1)).where(
            WhiteboardPage.channel_id == channel_id,
            WhiteboardPage.is_branch.is_(False),
            WhiteboardPage.is_deleted.is_(False),
        )
    )
    page = WhiteboardPage(
        channel_id=channel_id,
        title=payload.title,
        order_index=max_order + 1,
        created_by=current_user.id,
    )
    db.add(page)
    await db.commit()
    await db.refresh(page)
    return page


@router.get("/channels/{channel_id}/pages", response_model=list[PageRead])
async def list_pages(
    channel_id: UUID,
    _: ChannelMember = Depends(require_channel_role(MemberRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> list[WhiteboardPage]:
    pages = await db.scalars(
        select(WhiteboardPage)
        .where(
            WhiteboardPage.channel_id == channel_id,
            WhiteboardPage.is_branch.is_(False),
            WhiteboardPage.is_deleted.is_(False),
        )
        .order_by(WhiteboardPage.order_index.asc(), WhiteboardPage.created_at.asc())
    )
    return list(pages.all())


@router.patch("/pages/{page_id}", response_model=PageRead)
async def update_page(
    payload: PageUpdate,
    access: PageAccess = Depends(require_page_role(MemberRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> WhiteboardPage:
    page, _membership = access
    if payload.title is not None:
        page.title = payload.title

    if payload.order_index is not None and payload.order_index != page.order_index:
        old_index = page.order_index
        max_order = await db.scalar(
            select(func.coalesce(func.max(WhiteboardPage.order_index), 0)).where(
                WhiteboardPage.channel_id == page.channel_id,
                WhiteboardPage.is_branch.is_(False),
                WhiteboardPage.is_deleted.is_(False),
            )
        )
        new_index = min(payload.order_index, max_order)
        if new_index < old_index:
            await db.execute(
                update(WhiteboardPage)
                .where(
                    WhiteboardPage.channel_id == page.channel_id,
                    WhiteboardPage.id != page.id,
                    WhiteboardPage.is_branch.is_(False),
                    WhiteboardPage.is_deleted.is_(False),
                    WhiteboardPage.order_index >= new_index,
                    WhiteboardPage.order_index < old_index,
                )
                .values(order_index=WhiteboardPage.order_index + 1)
            )
        elif new_index > old_index:
            await db.execute(
                update(WhiteboardPage)
                .where(
                    WhiteboardPage.channel_id == page.channel_id,
                    WhiteboardPage.id != page.id,
                    WhiteboardPage.is_branch.is_(False),
                    WhiteboardPage.is_deleted.is_(False),
                    WhiteboardPage.order_index > old_index,
                    WhiteboardPage.order_index <= new_index,
                )
                .values(order_index=WhiteboardPage.order_index - 1)
            )
        page.order_index = new_index

    await db.commit()
    await db.refresh(page)
    return page


@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(
    access: PageAccess = Depends(require_page_role(MemberRole.EDITOR)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    page, _membership = access
    page.is_deleted = True
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/pages/{page_id}/elements", response_model=list[ElementRead])
async def list_elements(
    page_id: UUID,
    element_type: Annotated[ElementType | None, Query(alias="type")] = None,
    search: str | None = Query(default=None, min_length=1, max_length=200),
    _: PageAccess = Depends(require_page_role(MemberRole.VIEWER)),
    db: AsyncSession = Depends(get_db),
) -> list[WhiteboardElement]:
    conditions = [
        WhiteboardElement.page_id == page_id,
        WhiteboardElement.is_deleted.is_(False),
    ]
    if element_type is not None:
        conditions.append(WhiteboardElement.type == element_type)
    if search is not None:
        conditions.append(WhiteboardElement.content["text"].astext.ilike(f"%{search}%"))

    elements = await db.scalars(
        select(WhiteboardElement)
        .where(*conditions)
        .order_by(WhiteboardElement.created_at.asc())
    )
    return list(elements.all())


@router.post("/pages/{page_id}/elements", response_model=ElementRead, status_code=status.HTTP_201_CREATED)
async def create_element(
    page_id: UUID,
    payload: ElementCreate,
    access: PageAccess = Depends(require_page_role(MemberRole.EDITOR)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WhiteboardElement:
    _page, _membership = access
    element = WhiteboardElement(
        page_id=page_id,
        created_by=current_user.id,
        type=payload.type,
        transform=payload.transform,
        style=payload.style,
        content=payload.content,
    )
    db.add(element)
    await db.flush()
    await log_element_event(
        db,
        element=element,
        actor_id=current_user.id,
        operation=EventOperation.CREATE,
        before_state=None,
        after_state=element_state(element),
        vector_clock=payload.vector_clock,
    )
    await db.commit()
    await db.refresh(element)
    return element


@router.patch("/elements/{element_id}", response_model=ElementRead)
async def update_element(
    payload: ElementUpdate,
    access: ElementAccess = Depends(require_element_role(MemberRole.EDITOR)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WhiteboardElement:
    element, _page, membership = access
    update_data = payload.model_dump(exclude={"vector_clock"}, exclude_unset=True, exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No element fields to update")

    await assert_can_mutate_element(db, element, membership.role)
    before_state = element_state(element)
    for field, value in update_data.items():
        setattr(element, field, value)
    element.updated_at = datetime.now(UTC)
    await db.flush()
    await log_element_event(
        db,
        element=element,
        actor_id=current_user.id,
        operation=EventOperation.UPDATE,
        before_state=before_state,
        after_state=element_state(element),
        vector_clock=payload.vector_clock,
    )
    await db.commit()
    await db.refresh(element)
    return element


@router.delete("/elements/{element_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_element(
    access: ElementAccess = Depends(require_element_role(MemberRole.EDITOR)),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    element, _page, membership = access
    await assert_can_mutate_element(db, element, membership.role, deleting=True)
    before_state = element_state(element)
    element.is_deleted = True
    element.updated_at = datetime.now(UTC)
    await db.flush()
    await log_element_event(
        db,
        element=element,
        actor_id=current_user.id,
        operation=EventOperation.DELETE,
        before_state=before_state,
        after_state=element_state(element),
    )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
