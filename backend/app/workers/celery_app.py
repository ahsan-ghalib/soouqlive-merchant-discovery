"""Celery application (queue-isolated workers)."""

import os

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "soouq_merchant",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.discovery_tasks",
        "app.workers.enrichment_tasks",
        "app.workers.validation_tasks",
        "app.workers.scoring_tasks",
        "app.workers.export_tasks",
        "app.workers.scheduled_tasks",
        "app.workers.outreach_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=os.getenv("CELERY_TASK_ALWAYS_EAGER", "").lower() in {"1", "true", "yes"}
    or settings.app_env.lower() == "test",
    task_eager_propagates=True,
    task_routes={
        "app.workers.discovery_tasks.*": {"queue": "discovery"},
        "app.workers.enrichment_tasks.*": {"queue": "enrichment"},
        "app.workers.validation_tasks.*": {"queue": "validation"},
        "app.workers.scoring_tasks.*": {"queue": "scoring"},
        "app.workers.export_tasks.*": {"queue": "exports"},
        "app.workers.scheduled_tasks.*": {"queue": "maintenance"},
        "app.workers.outreach_tasks.*": {"queue": "outreach"},
    },
    task_default_queue="maintenance",
)
