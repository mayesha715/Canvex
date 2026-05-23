from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.models.channel import ChannelMember
from app.models.enums import MemberRole
from app.models.user import User

ROLE_RANK = {
    MemberRole.VIEWER: 1,
    MemberRole.EDITOR: 2,
    MemberRole.ADMIN: 3,
    MemberRole.OWNER: 4,
}


async def get_channel_membership(
    channel_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChannelMember:
    membership = await db.scalar(
        select(ChannelMember).where(
            ChannelMember.channel_id == channel_id,
            ChannelMember.user_id == current_user.id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this channel")
    return membership


def require_channel_role(minimum_role: MemberRole) -> Callable[..., object]:
    async def dependency(
        membership: ChannelMember = Depends(get_channel_membership),
    ) -> ChannelMember:
        if ROLE_RANK[membership.role] < ROLE_RANK[minimum_role]:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient channel role")
        return membership

    return dependency
