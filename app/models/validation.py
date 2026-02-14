"""ValidationRun model — tracks each validation execution."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending"
    )  # pending | running | completed | failed
    files: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict
    )  # {"payment_report": "file.xlsx", ...}
    error_counts: Mapped[dict] = mapped_column(
        JSONB, nullable=True, default=dict
    )  # {"duplicates": 5, "mismatches": 3, ...}
    warning_counts: Mapped[dict] = mapped_column(
        JSONB, nullable=True, default=dict
    )
    rule_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_file: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ValidationRun {self.id} [{self.status}]>"
