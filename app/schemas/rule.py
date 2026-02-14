"""Rule schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class RuleBase(BaseModel):
    name: str
    rule_type: str  # duplicate | match | existence | numeric_compare
    primary_field: str
    secondary_field: str | None = None
    operator: str | None = None  # eq | ne | gt | lt | gte | lte | contains | in
    tolerance: float | None = None
    severity: str = "error"  # error | warning
    description: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class RuleCreate(RuleBase):
    client_id: UUID | None = None  # None = global rule


class RuleUpdate(BaseModel):
    name: str | None = None
    rule_type: str | None = None
    primary_field: str | None = None
    secondary_field: str | None = None
    operator: str | None = None
    tolerance: float | None = None
    severity: str | None = None
    description: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    enabled: bool | None = None


class RuleResponse(RuleBase):
    id: UUID
    client_id: UUID | None
    enabled: bool
    version: int
    created_by: str
    approved_by: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RuleApproval(BaseModel):
    approved: bool
    reason: str | None = None
