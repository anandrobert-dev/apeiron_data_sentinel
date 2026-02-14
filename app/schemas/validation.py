"""Validation schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ValidationRunResponse(BaseModel):
    id: UUID
    client_id: UUID
    user_id: UUID
    status: str
    files: dict
    error_counts: dict | None
    warning_counts: dict | None
    rule_version: int | None
    result_file: str | None
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ValidationTrigger(BaseModel):
    client_id: UUID
    file_labels: dict[str, str] | None = None  # {"payment_report": "filename.xlsx"}
