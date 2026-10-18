from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from .extensions import db


class BlacklistEntry(db.Model):
    __tablename__ = "blacklist_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(db.String(254), unique=True, nullable=False)
    app_uuid: Mapped[UUID] = mapped_column(db.Uuid, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(db.String(255))
    source_ip: Mapped[str] = mapped_column(db.String(45), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
