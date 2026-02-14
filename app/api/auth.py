"""Authentication endpoints — login, register, refresh."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role, get_current_user, require_role
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return JWT token."""
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    token = create_access_token(data={"sub": str(user.id), "role": user.role})

    # Audit log
    db.add(AuditLog(
        action="user_login",
        entity_type="user",
        entity_id=str(user.id),
        user_id=user.id,
        username=user.username,
    ))

    return TokenResponse(
        access_token=token,
        role=user.role,
        username=user.username,
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.SUPER_ADMIN)),
):
    """Register a new user (SuperAdmin only)."""
    # Check for existing username/email
    existing = await db.execute(
        select(User).where(
            (User.username == request.username) | (User.email == request.email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    # Validate role
    valid_roles = [r.value for r in Role]
    if request.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {valid_roles}",
        )

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        role=request.role,
        client_ids=[UUID(cid) for cid in request.client_ids] if request.client_ids else [],
    )
    db.add(user)
    await db.flush()

    token = create_access_token(data={"sub": str(user.id), "role": user.role})

    # Audit log
    db.add(AuditLog(
        action="user_registered",
        entity_type="user",
        entity_id=str(user.id),
        user_id=current_user.id,
        username=current_user.username,
        details={"new_user": request.username, "role": request.role},
    ))

    return TokenResponse(
        access_token=token,
        role=user.role,
        username=user.username,
    )
