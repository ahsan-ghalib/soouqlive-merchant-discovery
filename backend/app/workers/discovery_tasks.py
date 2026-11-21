"""Celery discovery worker tasks."""

from __future__ import annotations

import logging
from uuid import UUID

from app.core.sync_database import SyncSessionLocal
from app.services.discovery_service import DiscoveryError, DiscoveryExecutionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _dispatch_followups(session) -> None:
    """After successful commit, queue enrichment + scoring follow-ups."""
    enrichment_ids = list(session.info.pop("pending_enrichment_ids", []) or [])
    score_ids = list(session.info.pop("pending_score_ids", []) or [])
    if enrichment_ids:
        from app.workers.enrichment_tasks import run_enrichment_job

        for eid in enrichment_ids:
            try:
                run_enrichment_job.delay(eid)
            except Exception:
                logger.exception("Failed to queue enrichment job %s", eid)
    if score_ids:
        from app.workers.scoring_tasks import score_business

        # Unique preserve order
        seen: set[str] = set()
        for bid in score_ids:
            if bid in seen:
                continue
            seen.add(bid)
            try:
                score_business.delay(bid)
            except Exception:
                logger.exception("Failed to queue scoring for %s", bid)


@celery_app.task(
    name="app.workers.discovery_tasks.run_discovery_job",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def run_discovery_job(self, job_id: str) -> dict:
    """Idempotent discovery execution for a single job id."""
    session = SyncSessionLocal()
    try:
        service = DiscoveryExecutionService(session)
        result = service.execute_job(UUID(job_id))
        session.commit()
        _dispatch_followups(session)
        return result
    except DiscoveryError as exc:
        session.rollback()
        logger.error("Discovery job %s failed: %s", job_id, exc.message)
        try:
            from datetime import datetime, timezone

            from app.models.discovery_job import DiscoveryJob

            session2 = SyncSessionLocal()
            try:
                job = session2.get(DiscoveryJob, UUID(job_id))
                if job and job.status not in {"cancelled", "completed"}:
                    job.status = "failed"
                    job.completed_at = datetime.now(timezone.utc)
                    session2.commit()
            finally:
                session2.close()
        except Exception:
            logger.exception("Failed to mark discovery job as failed")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {"status": "failed", "error": exc.message}
    except Exception as exc:
        session.rollback()
        logger.exception("Unexpected discovery failure for %s", job_id)
        raise self.retry(exc=exc)
    finally:
        session.close()
