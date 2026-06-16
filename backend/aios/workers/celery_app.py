from celery import Celery
from kombu import Exchange, Queue

from aios.config import settings

celery_app = Celery(
    "aios",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
    include=[
        "aios.workers.scheduler_tasks",
        "aios.workers.agent_tasks",
        "aios.workers.tool_tasks",
        "aios.workers.evaluator_tasks",
        "aios.workers.beat_tasks",
    ],
)

# ---------------------------------------------------------------------------
# Queue definitions
# ---------------------------------------------------------------------------

default_exchange = Exchange("aios", type="direct")

celery_app.conf.task_queues = (
    Queue("scheduler", default_exchange, routing_key="scheduler"),
    Queue("agents",    default_exchange, routing_key="agents"),
    Queue("tools",     default_exchange, routing_key="tools"),
    Queue("evaluator", default_exchange, routing_key="evaluator"),
)

celery_app.conf.task_default_queue = "agents"
celery_app.conf.task_default_exchange = "aios"
celery_app.conf.task_default_routing_key = "agents"

# Route tasks to their queues explicitly
celery_app.conf.task_routes = {
    "aios.workers.scheduler_tasks.*": {"queue": "scheduler"},
    "aios.workers.agent_tasks.*":     {"queue": "agents"},
    "aios.workers.tool_tasks.*":      {"queue": "tools"},
    "aios.workers.evaluator_tasks.*": {"queue": "evaluator"},
    "aios.workers.beat_tasks.*":      {"queue": "scheduler"},
}

# ---------------------------------------------------------------------------
# Serialisation & reliability
# ---------------------------------------------------------------------------

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,           # ack only after the task finishes
    task_reject_on_worker_lost=True,  # requeue if the worker dies mid-task
    worker_prefetch_multiplier=1,  # one task per worker at a time
    task_track_started=True,
    result_expires=3600,           # keep results in Redis for 1 hour
)

# ---------------------------------------------------------------------------
# Beat schedule (periodic tasks)
# ---------------------------------------------------------------------------

from celery.schedules import crontab  # noqa: E402

celery_app.conf.beat_schedule = {
    "monitor-heartbeats": {
        "task": "aios.workers.beat_tasks.monitor_heartbeats",
        "schedule": 30.0,  # every 30 seconds
    },
    "aggregate-metrics": {
        "task": "aios.workers.beat_tasks.aggregate_metrics",
        "schedule": 300.0,  # every 5 minutes
    },
}
