from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class WhiteboardPage(Base):
    __tablename__ = "whiteboard_pages"

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    channel_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    branch_of: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("whiteboard_pages.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'Untitled page'"))
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_branch: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
