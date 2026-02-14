"""GRACE AI Assistant — API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.rbac import get_current_user
from app.models.user import User
from app.services.grace_service import grace_service

router = APIRouter(prefix="/grace", tags=["GRACE AI Assistant"])


class ExplainRequest(BaseModel):
    record_summary: str
    rule_name: str
    rule_description: str


class SummarizeRequest(BaseModel):
    validation_summary: dict


class SuggestRuleRequest(BaseModel):
    description: str


class GraceResponse(BaseModel):
    response: str | dict
    source: str = "local_ollama"


@router.post("/explain", response_model=GraceResponse)
async def explain_failure(
    request: ExplainRequest,
    current_user: User = Depends(get_current_user),
):
    """Ask GRACE to explain why a record failed validation."""
    if not await grace_service.is_available():
        raise HTTPException(
            status_code=503,
            detail="GRACE AI is currently unavailable. Ollama service may be down.",
        )

    response = await grace_service.explain_failure(
        record_summary=request.record_summary,
        rule_name=request.rule_name,
        rule_description=request.rule_description,
    )

    return GraceResponse(response=response)


@router.post("/summarize", response_model=GraceResponse)
async def summarize_trends(
    request: SummarizeRequest,
    current_user: User = Depends(get_current_user),
):
    """Ask GRACE to summarize validation trends."""
    if not await grace_service.is_available():
        raise HTTPException(status_code=503, detail="GRACE AI unavailable")

    response = await grace_service.summarize_trends(request.validation_summary)
    return GraceResponse(response=response)


@router.post("/suggest-rule", response_model=GraceResponse)
async def suggest_rule(
    request: SuggestRuleRequest,
    current_user: User = Depends(get_current_user),
):
    """Ask GRACE to convert a natural language description into a rule draft."""
    if not await grace_service.is_available():
        raise HTTPException(status_code=503, detail="GRACE AI unavailable")

    response = await grace_service.suggest_rule(request.description)
    return GraceResponse(response=response)


@router.get("/status")
async def grace_status():
    """Check if GRACE AI assistant (Ollama) is available."""
    available = await grace_service.is_available()
    return {"available": available, "model": grace_service.model}
