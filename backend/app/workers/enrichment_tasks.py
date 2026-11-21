"""Celery enrichment worker tasks."""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.sync_database import SyncSessionLocal
from app.services.enrichment_service import EnrichmentError, EnrichmentExecutionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.enrichment_tasks.run_enrichment_job",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
)
def run_enrichment_job(self, job_id: str) -> dict:
    session = SyncSessionLocal()
    try:
        result = EnrichmentExecutionService(session).execute_job(UUID(job_id))
        session.commit()
        return result
    except EnrichmentError as exc:
        session.rollback()
        logger.error("Enrichment job %s failed: %s", job_id, exc.message)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "error": exc.message}
    except Exception as exc:
        session.rollback()
        logger.exception("Unexpected enrichment failure for %s", job_id)
        # Mark failed after retries exhausted
        try:
            from datetime import datetime, timezone

            from app.models.discovery_job import EnrichmentJob

            session2 = SyncSessionLocal()
            try:
                job = session2.get(EnrichmentJob, UUID(job_id))
                if job and job.status not in {"completed", "cancelled"}:
                    if self.request.retries >= self.max_retries:
                        job.status = "failed"
                        job.error_message = str(exc)
                        job.completed_at = datetime.now(timezone.utc)
                        session2.commit()
            finally:
                session2.close()
        except Exception:
            logger.exception("Failed to mark enrichment job failed")
        raise self.retry(exc=exc)
    finally:
        session.close()
