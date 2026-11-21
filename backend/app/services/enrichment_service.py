"""Website enrichment orchestration and persistence."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.enrichment.crawler import CrawlResult, WebsiteCrawler
from app.models.activity import Activity
from app.models.business import Business
from app.models.contact import BusinessContact
from app.models.discovery_job import EnrichmentJob
from app.models.source import DataProvider, LeadSource
from app.models.user import User
from app.utils.email import normalize_email
from app.utils.phone import normalize_phone

logger = logging.getLogger(__name__)


class EnrichmentError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


JOB_TYPES = {
    "website_discovery",
    "contact_extraction",
    "social_extraction",
    "data_validation",
    "classification",
}


class EnrichmentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_job(
        self,
        *,
        business_id: UUID,
        job_type: str = "website_discovery",
        user: Optional[User] = None,
        auto_start: bool = True,
    ) -> EnrichmentJob:
        if job_type not in JOB_TYPES:
            raise EnrichmentError(f"Invalid job_type. Allowed: {sorted(JOB_TYPES)}")
        business = await self.db.get(Business, business_id)
        if business is None:
            raise EnrichmentError("Business not found", 404)
        if job_type in {"website_discovery", "contact_extraction", "social_extraction"}:
            if not business.website_url:
                raise EnrichmentError("Business has no website_url to enrich", 400)

        job = EnrichmentJob(
            id=uuid.uuid4(),
            business_id=business_id,
            job_type=job_type,
            status="pending",
            scheduled_at=datetime.now(timezone.utc),
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.commit()

        if auto_start:
            from app.workers.enrichment_tasks import run_enrichment_job

            job.status = "queued"
            await self.db.flush()
            await self.db.commit()
            run_enrichment_job.delay(str(job.id))
            await self.db.refresh(job)
        return job

    async def create_bulk(
        self,
        business_ids: list[UUID],
        *,
        job_type: str = "website_discovery",
        user: Optional[User] = None,
    ) -> dict[str, Any]:
        created = []
        failed = []
        for business_id in business_ids:
            try:
                job = await self.create_job(
                    business_id=business_id,
                    job_type=job_type,
                    user=user,
                    auto_start=True,
                )
                created.append(str(job.id))
            except EnrichmentError as exc:
                failed.append({"business_id": str(business_id), "error": exc.message})
        return {"created": created, "failed": failed, "total_created": len(created)}

    async def get_job(self, job_id: UUID) -> EnrichmentJob:
        job = await self.db.get(EnrichmentJob, job_id)
        if job is None:
            raise EnrichmentError("Enrichment job not found", 404)
        return job

    async def list_jobs(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
        business_id: Optional[UUID] = None,
    ) -> tuple[list[EnrichmentJob], int]:
        from sqlalchemy import func

        stmt = select(EnrichmentJob)
        count_stmt = select(func.count()).select_from(EnrichmentJob)
        if status:
            stmt = stmt.where(EnrichmentJob.status == status)
            count_stmt = count_stmt.where(EnrichmentJob.status == status)
        if business_id:
            stmt = stmt.where(EnrichmentJob.business_id == business_id)
            count_stmt = count_stmt.where(EnrichmentJob.business_id == business_id)
        total = (await self.db.execute(count_stmt)).scalar_one()
        rows = (
            await self.db.execute(
                stmt.order_by(EnrichmentJob.created_at.desc())
                .offset((page - 1) * limit)
                .limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def results_for_business(self, business_id: UUID) -> dict[str, Any]:
        business = await self.db.get(Business, business_id)
        if business is None:
            raise EnrichmentError("Business not found", 404)
        jobs = (
            await self.db.execute(
                select(EnrichmentJob)
                .where(EnrichmentJob.business_id == business_id)
                .order_by(EnrichmentJob.created_at.desc())
            )
        ).scalars().all()
        contacts = (
            await self.db.execute(
                select(BusinessContact).where(BusinessContact.business_id == business_id)
            )
        ).scalars().all()
        return {
            "business_id": str(business_id),
            "website_url": business.website_url,
            "last_enriched_at": business.last_enriched_at.isoformat()
            if business.last_enriched_at
            else None,
            "jobs": [
                {
                    "id": str(j.id),
                    "job_type": j.job_type,
                    "status": j.status,
                    "result_summary": j.result_summary,
                    "error_message": j.error_message,
                    "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                }
                for j in jobs
            ],
            "contacts": [
                {
                    "id": str(c.id),
                    "contact_type": c.contact_type,
                    "contact_value": c.contact_value,
                    "is_verified": c.is_verified,
                    "verification_method": c.verification_method,
                }
                for c in contacts
            ],
        }


class EnrichmentExecutionService:
    """Sync execution path for Celery workers."""

    def __init__(self, session: Session, crawler: Optional[WebsiteCrawler] = None) -> None:
        self.session = session
        self.crawler = crawler or WebsiteCrawler()

    def execute_job(self, job_id: UUID) -> dict[str, Any]:
        job = self.session.get(EnrichmentJob, job_id)
        if job is None:
            raise EnrichmentError("Job not found", 404)
        if job.status in {"completed", "cancelled"}:
            return {"status": job.status, "skipped": True}

        business = self.session.get(Business, job.business_id)
        if business is None:
            job.status = "failed"
            job.error_message = "Business missing"
            job.completed_at = datetime.now(timezone.utc)
            self.session.flush()
            return {"status": "failed"}

        job.status = "processing"
        job.attempts = (job.attempts or 0) + 1
        self.session.flush()

        if job.job_type == "data_validation":
            summary = self._run_validation(business)
        else:
            if not business.website_url:
                job.status = "failed"
                job.error_message = "No website_url"
                job.completed_at = datetime.now(timezone.utc)
                self.session.flush()
                return {"status": "failed"}
            try:
                crawl = self.crawler.crawl(business.website_url)
            except Exception as exc:
                logger.exception("Crawl failed")
                job.status = "failed"
                job.error_message = str(exc)
                job.completed_at = datetime.now(timezone.utc)
                self.session.flush()
                if job.attempts < job.max_attempts:
                    raise
                return {"status": "failed", "error": str(exc)}

            if not crawl.robots_allowed and not crawl.pages:
                job.status = "failed"
                job.error_message = "; ".join(crawl.errors) or "robots disallowed"
                job.completed_at = datetime.now(timezone.utc)
                job.result_summary = {"errors": crawl.errors, "robots_allowed": False}
                self.session.flush()
                return {"status": "failed"}

            summary = self._persist_crawl(business, crawl)

        job.status = "completed"
        job.result_summary = summary
        job.error_message = None
        job.completed_at = datetime.now(timezone.utc)
        business.last_enriched_at = datetime.now(timezone.utc)
        self.session.flush()

        # Queue validation after successful contact extraction
        if job.job_type != "data_validation":
            validation = EnrichmentJob(
                id=uuid.uuid4(),
                business_id=business.id,
                job_type="data_validation",
                status="queued",
                scheduled_at=datetime.now(timezone.utc),
            )
            self.session.add(validation)
            self.session.flush()
            from app.workers.validation_tasks import run_validation_job

            run_validation_job.delay(str(validation.id))
        else:
            # After validation, queue lead scoring
            from app.workers.scoring_tasks import score_business

            score_business.delay(str(business.id), auto_qualify=True, qualify_threshold=60)

        return {"status": "completed", "summary": summary}

    def _persist_crawl(self, business: Business, crawl: CrawlResult) -> dict[str, Any]:
        provider = (
            self.session.execute(
                select(DataProvider).where(DataProvider.provider_type == "public_website")
            )
            .scalars()
            .first()
        )
        source = None
        if provider:
            source = LeadSource(
                id=uuid.uuid4(),
                business_id=business.id,
                provider_id=provider.id,
                source_type="public_website",
                source_url=crawl.start_url,
                external_reference=crawl.start_url,
                collection_method="website_crawl",
                policy_version=provider.policy_reference,
                permitted_purposes=["enrichment"],
                metadata_={
                    "pages": [p.final_url for p in crawl.pages],
                    "errors": crawl.errors,
                },
            )
            self.session.add(source)
            self.session.flush()

        emails_added = 0
        phones_added = 0
        social_added = 0

        for email in crawl.emails:
            emails_added += self._add_contact(
                business.id,
                "business_email",
                email,
                source_id=source.id if source else None,
            )
        for phone in crawl.phones:
            phones_added += self._add_contact(
                business.id,
                "business_phone",
                phone,
                source_id=source.id if source else None,
            )
        for social in crawl.social_profiles:
            social_added += self._add_contact(
                business.id,
                "social_profile",
                social["url"],
                label=social["network"],
                source_id=source.id if source else None,
            )

        # Fill missing description/address from structured data when empty
        structured = crawl.structured or {}
        if not business.address and structured.get("addresses"):
            business.address = structured["addresses"][0]
        if not business.business_name_ar and structured.get("names"):
            # Keep original name; optionally store alt name in description note only if empty
            pass

        self.session.add(
            Activity(
                id=uuid.uuid4(),
                business_id=business.id,
                activity_type="lead_discovered",
                description="Website enrichment completed",
                metadata_={
                    "emails_added": emails_added,
                    "phones_added": phones_added,
                    "social_added": social_added,
                    "pages_crawled": len(crawl.pages),
                },
            )
        )
        self.session.flush()
        return {
            "pages_crawled": len(crawl.pages),
            "emails_found": crawl.emails,
            "phones_found": crawl.phones,
            "social_profiles": crawl.social_profiles,
            "emails_added": emails_added,
            "phones_added": phones_added,
            "social_added": social_added,
            "errors": crawl.errors,
            "robots_allowed": crawl.robots_allowed,
            "structured": structured,
            "note": "Extracted public contacts are NOT marketing consent.",
        }

    def _add_contact(
        self,
        business_id: UUID,
        contact_type: str,
        value: str,
        *,
        label: Optional[str] = None,
        source_id: Optional[UUID] = None,
    ) -> int:
        if contact_type == "business_email":
            normalized = normalize_email(value)
        elif contact_type == "business_phone":
            normalized = normalize_phone(value)
        else:
            normalized = value.strip().lower()
        if not normalized:
            return 0

        exists = (
            self.session.execute(
                select(BusinessContact).where(
                    BusinessContact.business_id == business_id,
                    BusinessContact.contact_type == contact_type,
                    BusinessContact.normalized_value == normalized,
                ).limit(1)
            )
            .scalars()
            .first()
        )
        if exists:
            return 0

        self.session.add(
            BusinessContact(
                id=uuid.uuid4(),
                business_id=business_id,
                contact_type=contact_type,
                contact_value=value,
                normalized_value=normalized,
                label=label,
                is_primary=False,
                is_verified=False,
                source_id=source_id,
            )
        )
        return 1

    def _run_validation(self, business: Business) -> dict[str, Any]:
        from app.services.validation_service import ValidationService

        return ValidationService(self.session).validate_business(business)
