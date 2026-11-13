"""A bounded history of real service checks, never synthetic telemetry."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CheckRecord(Base):
    __tablename__ = "health_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    source: Mapped[str] = mapped_column(String(20))
    services: Mapped[list[dict]] = mapped_column(JSON)
