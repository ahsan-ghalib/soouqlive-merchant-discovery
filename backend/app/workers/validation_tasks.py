"""Celery validation worker tasks."""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.sync_database import SyncSessionLocal
from app.services.enrichment_service import EnrichmentError, EnrichmentExecutionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.validation_tasks.run_validation_job",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def run_validation_job(self, job_id: str) -> dict:
    session = SyncSessionLocal()
    try:
        result = EnrichmentExecutionService(session).execute_job(UUID(job_id))
        session.commit()
        return result
    except EnrichmentError as exc:
        session.rollback()
        logger.error("Validation job %s failed: %s", job_id, exc.message)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "error": exc.message}
    except Exception as exc:
        session.rollback()
        logger.exception("Unexpected validation failure for %s", job_id)
        raise self.retry(exc=exc)
    finally:
        session.close()
