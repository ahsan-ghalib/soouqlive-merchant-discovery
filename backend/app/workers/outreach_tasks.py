"""Celery tasks for paced email outreach."""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.sync_database import SyncSessionLocal
from app.services.outreach_service import OutreachExecutionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.outreach_tasks.process_email_blast", bind=True, max_retries=3)
def process_email_blast(self, blast_id: str) -> dict:
    with SyncSessionLocal() as session:
        try:
            result = OutreachExecutionService(session).process_next(UUID(blast_id))
            logger.info("Email blast %s => %s", blast_id, result.get("status"))
            return result
        except Exception as exc:
            logger.exception("Email blast processing failed: %s", blast_id)
            session.rollback()
            raise self.retry(exc=exc, countdown=120) from exc
