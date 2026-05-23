from datetime import date
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, PrimaryKeyConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CanvasAnalytics(Base):
    __tablename__ = "canvas_analytics"
    __table_args__ = (
        PrimaryKeyConstraint(
            "page_id",
            "user_id",
            "session_date",
            "region_x_bucket",
            "region_y_bucket",
        ),
    )

    page_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("whiteboard_pages.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_date: Mapped[date] = mapped_column(nullable=False)
    region_x_bucket: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    region_y_bucket: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    edit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    time_on_canvas_s: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
