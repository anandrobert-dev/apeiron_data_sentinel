"""Health check endpoint — verifies DB, Redis, and Ollama connectivity."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """
    System health check — used by Docker, Nginx, and monitoring.
    Returns status of all dependent services.
    """
    health = {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "checks": {},
    }

    # --- Check PostgreSQL ---
    try:
        from sqlalchemy import text
        from app.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        health["checks"]["database"] = "ok"
    except Exception as e:
        health["checks"]["database"] = f"error: {str(e)[:100]}"
        health["status"] = "degraded"

    # --- Check Redis ---
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        health["checks"]["redis"] = "ok"
    except Exception as e:
        health["checks"]["redis"] = f"error: {str(e)[:100]}"
        health["status"] = "degraded"

    # --- Check Ollama ---
    try:
        import httpx

        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                health["checks"]["ollama"] = "ok"
            else:
                health["checks"]["ollama"] = f"status: {resp.status_code}"
                health["status"] = "degraded"
    except Exception:
        health["checks"]["ollama"] = "unavailable"
        # Ollama being down doesn't degrade the system

    return health
