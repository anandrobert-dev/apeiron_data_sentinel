"""Validation API — file upload, trigger validation, get results."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.rbac import get_current_user
from app.database import get_db
from app.engine.loader import load_file, save_upload, validate_upload
from app.engine.reporter import generate_excel_report
from app.engine.validator import apply_rules, load_active_rules
from app.models.audit_log import AuditLog
from app.models.client import Client
from app.models.user import User
from app.models.validation import ValidationRun
from app.schemas.validation import ValidationRunResponse

router = APIRouter(prefix="/validation", tags=["Validation"])


@router.post("/run/{client_id}", response_model=ValidationRunResponse | dict)
async def run_validation(
    client_id: str,
    files: list[UploadFile] = File(...),
    rule_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload files and trigger a validation run for a client.
    Files must be CSV or Excel (max 100MB each).
    Optional: filter by rule_type (e.g., 'duplicate').
    """
    # Validate client
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    run_id = str(uuid.uuid4())
    file_map = {}
    dataframes = {}

    # Process uploaded files
    for upload_file in files:
        content = await upload_file.read()
        validate_upload(upload_file.filename, len(content))

        # Save to disk
        filepath = save_upload(content, upload_file.filename, client.code, run_id)
        label = upload_file.filename.rsplit(".", 1)[0].lower().replace(" ", "_")
        file_map[label] = upload_file.filename

        # Load into Polars
        df = load_file(filepath)
        dataframes[label] = df

    if not dataframes:
        raise HTTPException(
            status_code=400, detail="No valid files uploaded"
        )

    # Load rules (filtered by type if provided)
    rules = await load_active_rules(db, client_id=client_id, rule_type=rule_type)

    # Check if any file looks like a GL reference
    gl_ref = None
    for label, df in dataframes.items():
        if "gl_code" in df.columns and df.width <= 5:
            gl_ref = df
            break

    # Run validation
    results = apply_rules(rules, dataframes, gl_reference=gl_ref)

    # Generate report
    report_path = None
    if results["issues"]:
        from pathlib import Path

        report_filename = f"validation_{client.code}_{run_id[:8]}.xlsx"
        report_path_obj = Path(settings.upload_dir) / client.code / run_id / report_filename
        generate_excel_report(
            issues=results["issues"],
            summary=results["summary"],
            output_path=report_path_obj,
        )
        report_path = str(report_path_obj)

    # Save validation run
    validation_run = ValidationRun(
        id=uuid.UUID(run_id),
        client_id=uuid.UUID(client_id),
        user_id=current_user.id,
        status="completed",
        files=file_map,
        error_counts=results["error_counts"],
        warning_counts=results["warning_counts"],
        rule_version=max((r.version for r in rules), default=0),
        result_file=report_path,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(validation_run)

    # Audit log
    db.add(AuditLog(
        action="validation_run",
        entity_type="validation",
        entity_id=run_id,
        user_id=current_user.id,
        username=current_user.username,
        details={
            "client_code": client.code,
            "rule_type_filter": rule_type,
            "files": list(file_map.keys()),
            "total_errors": results["total_errors"],
            "total_warnings": results["total_warnings"],
            "rules_applied": results["rules_applied"],
        },
    ))

    # Return simple JSON if duplicate check requested
    if rule_type == "duplicate":
        return {
            "total_records": results.get("total_records", 0),
            "duplicates_found": results.get("duplicates_found", 0),
            "duplicate_fields": results.get("duplicate_fields", []),
            "sample_rows": results.get("sample_rows", []),
            "warnings": results.get("warning_counts", {}),
        }

    return validation_run


@router.get("/history/{client_id}", response_model=list[ValidationRunResponse])
async def get_validation_history(
    client_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get validation run history for a client."""
    result = await db.execute(
        select(ValidationRun)
        .where(ValidationRun.client_id == client_id)
        .order_by(ValidationRun.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/run/{run_id}", response_model=ValidationRunResponse)
async def get_validation_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific validation run by ID."""
    result = await db.execute(
        select(ValidationRun).where(ValidationRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found")
    return run
