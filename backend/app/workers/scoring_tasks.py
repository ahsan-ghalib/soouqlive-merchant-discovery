"""Celery scoring worker tasks."""

from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from app.core.sync_database import SyncSessionLocal
from app.services.scoring_service import ScoringService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.scoring_tasks.score_business",
    bind=True,
    max_retries=3,
    default_retry_delay=20,
    acks_late=True,
)
def score_business(
    self,
    business_id: str,
    auto_qualify: bool = True,
    qualify_threshold: int = 60,
    user_id: Optional[str] = None,
) -> dict:
    session = SyncSessionLocal()
    try:
        breakdown = ScoringService(session).score_business_sync(
            UUID(business_id),
            user_id=UUID(user_id) if user_id else None,
            auto_qualify=auto_qualify,
            qualify_threshold=qualify_threshold,
        )
        session.commit()
        return {
            "business_id": business_id,
            "score": breakdown.total,
            "components": breakdown.components,
        }
    except Exception as exc:
        session.rollback()
        logger.exception("Scoring failed for %s", business_id)
        raise self.retry(exc=exc)
    finally:
        session.close()


@celery_app.task(
    name="app.workers.scoring_tasks.score_businesses_bulk",
    acks_late=True,
)
def score_businesses_bulk(
    business_ids: list[str],
    auto_qualify: bool = True,
    qualify_threshold: int = 60,
) -> dict:
    session = SyncSessionLocal()
    results = []
    try:
        service = ScoringService(session)
        for business_id in business_ids:
            try:
                breakdown = service.score_business_sync(
                    UUID(business_id),
                    auto_qualify=auto_qualify,
                    qualify_threshold=qualify_threshold,
                )
                results.append(
                    {
                        "id": business_id,
                        "status": "ok",
                        "score": breakdown.total,
                        "components": breakdown.components,
                    }
                )
            except Exception as exc:
                results.append({"id": business_id, "status": "failed", "error": str(exc)})
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    return {"results": results, "total": len(results)}
