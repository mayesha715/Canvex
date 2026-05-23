from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    channel_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    signing_secret: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("encode(gen_random_bytes(32), 'hex')"))
    event_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
