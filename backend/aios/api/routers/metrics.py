import json

import redis as _redis
from fastapi import APIRouter

from aios.config import settings

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/summary")
async def metrics_summary():
    r = _redis.from_url(settings.redis_url, decode_responses=True)
    cached = r.get("metrics:summary")
    if cached:
        return json.loads(cached)
    # Fallback if beat hasn't run yet
    return {
        "jobs_completed_last_24h": 0,
        "jobs_failed_last_24h": 0,
        "success_rate_7d": 0.0,
        "active_jobs_count": 0,
        "total_tokens_today": 0,
        "total_cost_today": 0.0,
        "avg_job_duration_ms": 0,
        "computed_at": None,
    }
