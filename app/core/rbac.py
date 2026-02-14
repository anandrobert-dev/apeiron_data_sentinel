"""Role-Based Access Control (RBAC) — roles, permissions, and FastAPI dependencies."""

import enum
from functools import wraps
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import User

security_scheme = HTTPBearer()


class Role(str, enum.Enum):
    SUPER_ADMIN = "SuperAdmin"
    RULE_APPROVER = "RuleApprover"
    ACCOUNT_MANAGER = "AccountManager"
    VALIDATOR_USER = "ValidatorUser"
    AUDITOR = "Auditor"


# Permission hierarchy — higher roles include lower permissions
ROLE_HIERARCHY = {
    Role.SUPER_ADMIN: 100,
    Role.RULE_APPROVER: 80,
    Role.ACCOUNT_MANAGER: 60,
    Role.VALIDATOR_USER: 40,
    Role.AUDITOR: 20,
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract and validate the current user from the JWT bearer token.
    This is the primary authentication dependency.
    """
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


def require_role(*allowed_roles: Role):
    """
    FastAPI dependency factory — restricts endpoint to specific roles.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_role(Role.SUPER_ADMIN))])
    """
    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        user_role = current_user.role
        if user_role not in [r.value for r in allowed_roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not authorized for this action",
            )
        return current_user

    return role_checker


def require_client_access(client_id_param: str = "client_id"):
    """
    Dependency factory — ensures user has access to the specified client.
    SuperAdmin and RuleApprover have access to all clients.
    AccountManager and ValidatorUser must be assigned to the client.
    """
    async def client_access_checker(
        current_user: User = Depends(get_current_user),
        **kwargs,
    ) -> User:
        if current_user.role in (Role.SUPER_ADMIN.value, Role.RULE_APPROVER.value):
            return current_user

        # For other roles, check client assignment
        if current_user.client_ids and kwargs.get(client_id_param):
            requested_client = UUID(str(kwargs[client_id_param]))
            if requested_client in current_user.client_ids:
                return current_user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this client",
        )

    return client_access_checker
