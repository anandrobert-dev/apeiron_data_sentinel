"""Rules CRUD and approval workflow endpoints."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import Role, get_current_user, require_role
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.rule import Rule, RuleHistory
from app.models.user import User
from app.schemas.rule import RuleApproval, RuleCreate, RuleResponse, RuleUpdate

router = APIRouter(prefix="/rules", tags=["Rules"])


@router.get("/", response_model=list[RuleResponse])
async def list_rules(
    client_id: UUID | None = None,
    rule_type: str | None = None,
    enabled_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List rules, optionally filtered by client and/or type."""
    query = select(Rule)
    if client_id:
        query = query.where(
            (Rule.client_id == client_id) | (Rule.client_id.is_(None))
        )
    if rule_type:
        query = query.where(Rule.rule_type == rule_type)
    if enabled_only:
        today = date.today()
        query = query.where(
            Rule.enabled == True,
            Rule.approved_by.isnot(None),
            (Rule.effective_from.is_(None) | (Rule.effective_from <= today)),
            (Rule.effective_to.is_(None) | (Rule.effective_to >= today)),
        )
    query = query.order_by(Rule.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule: RuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(Role.SUPER_ADMIN, Role.ACCOUNT_MANAGER)
    ),
):
    """
    Create a new validation rule.
    AccountManagers can create rules for their assigned clients only.
    Rules are created as disabled — must be approved to activate.
    """
    # AccountManager can only create rules for their assigned clients
    if current_user.role == Role.ACCOUNT_MANAGER.value:
        if rule.client_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="AccountManagers cannot create global rules",
            )
        if current_user.client_ids and rule.client_id not in current_user.client_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this client",
            )

    db_rule = Rule(
        **rule.model_dump(),
        created_by=current_user.username,
        enabled=False,  # Always starts disabled
    )
    db.add(db_rule)
    await db.flush()

    # Create initial history entry
    db.add(RuleHistory(
        rule_id=db_rule.id,
        version=1,
        rule_type=db_rule.rule_type,
        primary_field=db_rule.primary_field,
        secondary_field=db_rule.secondary_field,
        operator=db_rule.operator,
        tolerance=db_rule.tolerance,
        severity=db_rule.severity,
        enabled=False,
        changed_by=current_user.username,
        change_reason="Rule created",
    ))

    # Audit log
    db.add(AuditLog(
        action="rule_created",
        entity_type="rule",
        entity_id=str(db_rule.id),
        user_id=current_user.id,
        username=current_user.username,
        details={"rule_name": db_rule.name, "rule_type": db_rule.rule_type},
    ))

    return db_rule


@router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: UUID,
    update: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(Role.SUPER_ADMIN, Role.ACCOUNT_MANAGER)
    ),
):
    """Update a rule. Bumps version and creates history snapshot."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rule, field, value)

    rule.version += 1
    rule.approved_by = None  # Reset approval on change
    rule.enabled = False

    # History snapshot
    db.add(RuleHistory(
        rule_id=rule.id,
        version=rule.version,
        rule_type=rule.rule_type,
        primary_field=rule.primary_field,
        secondary_field=rule.secondary_field,
        operator=rule.operator,
        tolerance=rule.tolerance,
        severity=rule.severity,
        enabled=rule.enabled,
        changed_by=current_user.username,
        change_reason="Rule updated",
    ))

    db.add(AuditLog(
        action="rule_updated",
        entity_type="rule",
        entity_id=str(rule.id),
        user_id=current_user.id,
        username=current_user.username,
        details={"version": rule.version, "changes": list(update_data.keys())},
    ))

    return rule


@router.post("/{rule_id}/approve", response_model=RuleResponse)
async def approve_rule(
    rule_id: UUID,
    approval: RuleApproval,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(Role.SUPER_ADMIN, Role.RULE_APPROVER)
    ),
):
    """
    Approve or reject a rule.
    Only RuleApprover and SuperAdmin can approve.
    Approver cannot be the same person who created the rule (unless SuperAdmin).
    """
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Prevent self-approval unless SuperAdmin
    if (
        rule.created_by == current_user.username
        and current_user.role != Role.SUPER_ADMIN.value
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot approve your own rule",
        )

    if approval.approved:
        rule.approved_by = current_user.username
        rule.enabled = True
    else:
        rule.approved_by = None
        rule.enabled = False

    db.add(AuditLog(
        action="rule_approved" if approval.approved else "rule_rejected",
        entity_type="rule",
        entity_id=str(rule.id),
        user_id=current_user.id,
        username=current_user.username,
        details={"approved": approval.approved, "reason": approval.reason},
    ))

    return rule


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific rule."""
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule
