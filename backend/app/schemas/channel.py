from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import MemberRole


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_private: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Channel name cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_private: bool | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Channel name cannot be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class ChannelRead(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    owner_id: UUID
    is_private: bool
    invite_code: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChannelListItem(ChannelRead):
    role: MemberRole


class MemberRead(BaseModel):
    user_id: UUID
    email: str
    display_name: str
    avatar_url: str | None = None
    role: MemberRole
    joined_at: datetime


class PageSummary(BaseModel):
    id: UUID
    title: str
    order_index: int
    is_branch: bool
    branch_of: UUID | None = None
    created_at: datetime


class ChannelDetail(ChannelRead):
    role: MemberRole
    members: list[MemberRead]
    pages: list[PageSummary]


class MemberRoleUpdate(BaseModel):
    role: MemberRole


class InviteCreate(BaseModel):
    role_on_join: MemberRole = MemberRole.EDITOR
    max_uses: int | None = Field(default=None, ge=1, le=1000)
    expires_at: datetime | None = None

    @field_validator("role_on_join")
    @classmethod
    def reject_owner_invites(cls, value: MemberRole) -> MemberRole:
        if value == MemberRole.OWNER:
            raise ValueError("Invite role cannot be owner")
        return value

    @field_validator("expires_at")
    @classmethod
    def validate_future_expiry(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        candidate = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if candidate <= datetime.now(UTC):
            raise ValueError("expires_at must be in the future")
        return candidate


class InviteRead(BaseModel):
    id: UUID
    channel_id: UUID
    code: str
    invite_url: str
    role_on_join: MemberRole
    max_uses: int | None = None
    uses_count: int
    expires_at: datetime | None = None
    created_at: datetime
