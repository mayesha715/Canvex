from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, PrimaryKeyConstraint, Text, func, text
from sqlalchemy.dialects.postgresql import ENUM, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import MemberRole

member_role_enum = ENUM(MemberRole, name="member_role", values_callable=lambda enum: [item.value for item in enum])


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    invite_code: Mapped[str | None] = mapped_column(Text, unique=True, server_default=text("encode(gen_random_bytes(6), 'hex')"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChannelMember(Base):
    __tablename__ = "channel_members"
    __table_args__ = (PrimaryKeyConstraint("channel_id", "user_id"),)

    channel_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[MemberRole] = mapped_column(member_role_enum, nullable=False, server_default=MemberRole.EDITOR.value)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class ChannelInvite(Base):
    __tablename__ = "channel_invites"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    channel_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True, server_default=text("encode(gen_random_bytes(8), 'hex')"))
    role_on_join: Mapped[MemberRole] = mapped_column(member_role_enum, nullable=False, server_default=MemberRole.EDITOR.value)
    max_uses: Mapped[int | None] = mapped_column(Integer)
    uses_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
