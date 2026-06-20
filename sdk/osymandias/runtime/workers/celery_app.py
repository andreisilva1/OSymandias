from celery import Celery
from kombu import Exchange, Queue

from osymandias.runtime.config import settings

celery_app = Celery(
    "osymandias",
    broker=settings.osy_rabbitmq_url,
    backend=settings.osy_redis_url,
    include=[
        "osymandias.runtime.workers.scheduler_tasks",
        "osymandias.runtime.workers.agent_tasks",
        "osymandias.runtime.workers.tool_tasks",
        "osymandias.runtime.workers.evaluator_tasks",
        "osymandias.runtime.workers.beat_tasks",
        "osymandias.runtime.workers.webhook_tasks",
    ],
)

# ---------------------------------------------------------------------------
# Queue definitions
# ---------------------------------------------------------------------------

default_exchange = Exchange("osymandias", type="direct")

celery_app.conf.task_queues = (
    Queue("scheduler", default_exchange, routing_key="scheduler"),
    Queue("agents",    default_exchange, routing_key="agents"),
    Queue("tools",     default_exchange, routing_key="tools"),
    Queue("evaluator", default_exchange, routing_key="evaluator"),
)

celery_app.conf.task_default_queue = "agents"
celery_app.conf.task_default_exchange = "osymandias"
celery_app.conf.task_default_routing_key = "agents"

# Route tasks to their queues explicitly
celery_app.conf.task_routes = {
    "osymandias.runtime.workers.scheduler_tasks.*": {"queue": "scheduler"},
    "osymandias.runtime.workers.agent_tasks.*":     {"queue": "agents"},
    "osymandias.runtime.workers.tool_tasks.*":      {"queue": "tools"},
    "osymandias.runtime.workers.evaluator_tasks.*": {"queue": "evaluator"},
    "osymandias.runtime.workers.beat_tasks.*":      {"queue": "scheduler"},
    "osymandias.runtime.workers.webhook_tasks.*":   {"queue": "tools"},
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
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=3600,
)

# ---------------------------------------------------------------------------
# Beat schedule (periodic tasks)
# ---------------------------------------------------------------------------

from celery.schedules import crontab  # noqa: E402

celery_app.conf.beat_schedule = {
    "monitor-heartbeats": {
        "task": "osymandias.runtime.workers.beat_tasks.monitor_heartbeats",
        "schedule": 30.0,
    },
    "aggregate-metrics": {
        "task": "osymandias.runtime.workers.beat_tasks.aggregate_metrics",
        "schedule": 300.0,
    },
}
