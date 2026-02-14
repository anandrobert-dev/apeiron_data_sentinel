"""Client management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role, get_current_user, require_role
from app.database import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientResponse, ClientUpdate

router = APIRouter(prefix="/clients", tags=["Clients"])


@router.get("/", response_model=list[ClientResponse])
async def list_clients(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all active clients."""
    result = await db.execute(
        select(Client).where(Client.is_active == True).order_by(Client.name)
    )
    return result.scalars().all()


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    client: ClientCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.SUPER_ADMIN)),
):
    """Create a new client (SuperAdmin only)."""
    existing = await db.execute(
        select(Client).where(Client.code == client.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Client with code '{client.code}' already exists",
        )

    db_client = Client(**client.model_dump())
    db.add(db_client)
    await db.flush()
    return db_client


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Get a specific client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    update: ClientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_role(Role.SUPER_ADMIN)),
):
    """Update client details."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

    return client
