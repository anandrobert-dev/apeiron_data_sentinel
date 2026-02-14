"""Client schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ClientBase(BaseModel):
    name: str
    code: str
    config: dict | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class ClientResponse(ClientBase):
    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
