"""Scheduled/maintenance tasks scaffold."""

from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.scheduled_tasks.ping")
def ping() -> str:
    return "ok"
