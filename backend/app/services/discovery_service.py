"""Discovery job orchestration and persistence."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.compliance.source_policy import (
    SourcePolicyError,
    build_persistable_payload,
    enforce_can_search,
    preview_safe_record,
    retention_expires_at,
)
from app.models.activity import Activity
from app.models.business import Business
from app.models.category import BusinessCategory
from app.models.contact import BusinessContact
from app.models.discovery_job import DiscoveryJob, EnrichmentJob
from app.models.location import Country, Location
from app.models.source import DataProvider, LeadSource
from app.models.user import User
from app.providers.base import BusinessProvider, ProviderBusinessRecord, ProviderSearchQuery
from app.providers.coverage import build_city_coverage_plan, build_coverage_queries
from app.providers.registry import get_provider
from app.services.deduplication_service import DeduplicationService
from app.utils.arabic import normalize_business_name
from app.utils.email import normalize_email
from app.utils.phone import normalize_phone

logger = logging.getLogger(__name__)


def _monetization_packs(*, has_website: bool, category: Optional[str]) -> list[str]:
    """Sales packs derived from directory signals (not Google content itself)."""
    packs: list[str] = []
    cat = (category or "").lower()
    if not has_website:
        packs.append("no_website_site_build")
    else:
        packs.append("website_upgrade")
    if any(k in cat for k in ("restaurant", "cafe", "bakery", "food")):
        packs.append("restaurant_portal")
    if any(k in cat for k in ("real_estate", "real-estate", "realtor")):
        packs.append("real_estate_portal")
    return packs


def _run_async(coro):
    """Run an async coroutine from sync Celery workers safely."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    # Already inside an event loop (e.g. pytest-asyncio): run in a thread.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class DiscoveryError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


TERMINAL_STATUSES = {"completed", "partially_completed", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "processing"}


def _split_keywords(keywords: list[str], language: str) -> tuple[str, Optional[str]]:
    english = None
    arabic = None
    for kw in keywords:
        if any("\u0600" <= ch <= "\u06FF" for ch in kw):
            arabic = arabic or kw
        else:
            english = english or kw
    if language == "ar":
        return arabic or english or (keywords[0] if keywords else "business"), arabic
    if language == "en":
        return english or (keywords[0] if keywords else "business"), arabic
    return english or (keywords[0] if keywords else "business"), arabic


class DiscoveryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def resolve_references(
        self,
        *,
        country_code: str = "SA",
        city: Optional[str] = None,
        category: Optional[str] = None,
        country_id: Optional[UUID] = None,
        location_id: Optional[UUID] = None,
        category_id: Optional[UUID] = None,
        provider_key: str,
    ) -> tuple[Optional[Country], Optional[Location], Optional[BusinessCategory], DataProvider]:
        country: Optional[Country] = None
        if country_id:
            country = await self.db.get(Country, country_id)
        elif country_code:
            result = await self.db.execute(
                select(Country).where(Country.iso_code == country_code.upper())
            )
            country = result.scalar_one_or_none()

        location: Optional[Location] = None
        if location_id:
            location = await self.db.get(Location, location_id)
        elif city and country:
            result = await self.db.execute(
                select(Location).where(
                    Location.country_id == country.id,
                    Location.location_type == "city",
                    func.lower(Location.name) == city.lower(),
                )
            )
            location = result.scalar_one_or_none()
            if location is None:
                result = await self.db.execute(
                    select(Location).where(
                        Location.country_id == country.id,
                        Location.slug == city.lower().replace(" ", "-"),
                    )
                )
                location = result.scalar_one_or_none()

        category_obj: Optional[BusinessCategory] = None
        if category_id:
            category_obj = await self.db.get(BusinessCategory, category_id)
        elif category:
            result = await self.db.execute(
                select(BusinessCategory).where(
                    or_slug_or_name(category)
                )
            )
            category_obj = result.scalar_one_or_none()

        provider_row = await self._resolve_provider_row(provider_key)
        return country, location, category_obj, provider_row

    async def _resolve_provider_row(self, provider_key: str) -> DataProvider:
        # Match by type key, exact name, or alias
        result = await self.db.execute(
            select(DataProvider).where(
                DataProvider.is_active.is_(True),
            )
        )
        providers = list(result.scalars().all())
        key = provider_key.strip().lower()
        for p in providers:
            if p.provider_type.lower() == key:
                return p
            if p.name.lower() == key:
                return p
            if key in {"places_api", "google_places", "google places api"} and (
                p.provider_type == "official_api" and "google" in p.name.lower()
            ):
                return p
            if key == "licensed_directory" and p.provider_type == "licensed_directory":
                return p
            if key == "manual_import" and p.provider_type == "manual_import":
                return p
        raise DiscoveryError(f"Provider '{provider_key}' not found or inactive", 404)

    async def create_coverage_sweep(
        self,
        payload: dict[str, Any],
        user: User,
    ) -> dict[str, Any]:
        """Create many discovery jobs (district/cuisine grid) for broader Places coverage."""
        city = payload.get("city") or "Riyadh"
        category = payload.get("category") or "restaurants"
        mode = payload.get("mode") or "districts"
        provider = payload.get("provider") or "places_api"
        limit_per = int(payload.get("limit_per_query") or 60)
        auto_start = bool(payload.get("auto_start", True))
        max_jobs = int(payload.get("max_jobs") or 40)

        specs = build_coverage_queries(
            city=city,
            category=category,
            mode=mode,
            custom_areas=payload.get("areas") or None,
            custom_keywords=payload.get("keywords") or None,
        )[:max_jobs]

        created_jobs: list[DiscoveryJob] = []
        for spec in specs:
            # Encode district into city-like search text via keyword + city param
            # Places builds: "{keyword} in {city}" — so pass area in city slot when district mode
            search_city = (
                f"{spec['area']}, {city}"
                if mode in {"districts", "full"} and spec.get("area") and spec["area"] != city
                else city
            )
            job = await self.create_job(
                {
                    "name": spec["name"][:255],
                    "country_code": payload.get("country_code") or "SA",
                    "city": search_city,
                    "category": category,
                    "keywords": [spec["keyword"]],
                    "search_keyword": spec["keyword"],
                    "provider": provider,
                    "limit": limit_per,
                    "language": payload.get("language") or "en",
                },
                user,
                auto_start=False,
            )
            # Stash coverage metadata
            params = dict(job.search_parameters or {})
            params["coverage"] = {
                "mode": mode,
                "area": spec.get("area"),
                "text": spec.get("text"),
            }
            job.search_parameters = params
            created_jobs.append(job)

        await self.db.flush()

        started = 0
        if auto_start:
            for job in created_jobs:
                try:
                    await self.start_job(job.id, user)
                    started += 1
                except DiscoveryError:
                    logger.exception("Failed to auto-start coverage job %s", job.id)

        return {
            "mode": mode,
            "city": city,
            "category": category,
            "queries_planned": len(specs),
            "jobs_created": len(created_jobs),
            "jobs_started": started,
            "limit_per_query": limit_per,
            "job_ids": [str(j.id) for j in created_jobs],
            "note": (
                "Places soft-caps ~60 unique results per query. "
                "Coverage sweep runs many district/cuisine queries; dedupe merges by place_id."
            ),
        }

    async def create_city_scrape(
        self,
        payload: dict[str, Any],
        user: User,
    ) -> dict[str, Any]:
        """One discovery job that fans out Places queries across a whole city."""
        city = (payload.get("city") or "Riyadh").strip()
        country_code = (payload.get("country_code") or "SA").strip().upper()
        category = payload.get("category") or "all"
        provider = payload.get("provider") or "places_api"
        limit_per = int(payload.get("limit_per_query") or 60)
        # Food scrapes need denser coverage (Riyadh-scale)
        foodish = str(category).lower() in {"restaurants", "cafes", "restaurant", "cafe"}
        max_queries = int(payload.get("max_queries") or (250 if foodish else 100))
        grid = int(payload.get("grid") or (7 if foodish else 5))
        auto_start = bool(payload.get("auto_start", True))
        language = payload.get("language") or "en"

        latitude = payload.get("latitude")
        longitude = payload.get("longitude")
        radius_km = payload.get("radius_km")
        location_id = payload.get("location_id")

        if location_id and (latitude is None or longitude is None):
            loc = await self.db.get(Location, UUID(str(location_id)))
            if loc is not None:
                if loc.latitude is not None:
                    latitude = float(loc.latitude)
                if loc.longitude is not None:
                    longitude = float(loc.longitude)
                if not city:
                    city = loc.name

        plan = build_city_coverage_plan(
            city=city,
            country_code=country_code,
            category=category,
            latitude=float(latitude) if latitude is not None else None,
            longitude=float(longitude) if longitude is not None else None,
            radius_km=float(radius_km) if radius_km is not None else None,
            max_queries=max_queries,
            limit_per_query=limit_per,
            grid=grid,
            keywords=payload.get("keywords") or None,
        )

        adapter = get_provider("places_api")
        # Cap by Places daily quota — prefer breadth: more queries, fewer pages each
        # Estimate ~3 API pages per subquery when limit_per≈60
        pages_per = max(1, (limit_per + 19) // 20)
        budget_queries = max(1, adapter.daily_quota // pages_per)
        if len(plan) > budget_queries:
            # Keep early district queries + sample later keywords/grid
            head = plan[: max(budget_queries // 2, 1)]
            rest = plan[len(head) :]
            step = max(1, len(rest) // max(budget_queries - len(head), 1))
            sampled = rest[::step][: max(budget_queries - len(head), 0)]
            plan = (head + sampled)[:budget_queries]

        total_expected = max(len(plan) * limit_per, limit_per)
        search_kw = category if category and category != "all" else "business"

        job = await self.create_job(
            {
                "name": (payload.get("name") or f"Full city scrape — {city}")[:255],
                "country_code": country_code,
                "city": city,
                "category": None if category == "all" else category,
                "keywords": [search_kw],
                "search_keyword": search_kw,
                "provider": provider,
                "limit": total_expected,
                "language": language,
                "location_id": location_id,
                "country_id": payload.get("country_id"),
                "category_id": payload.get("category_id"),
                "search_parameters": {
                    "city_full": True,
                    "coverage_plan": plan,
                    "limit_per_query": limit_per,
                    "max_queries": len(plan),
                    "grid": grid,
                    "category": category,
                    "latitude": latitude,
                    "longitude": longitude,
                },
            },
            user,
            auto_start=False,
        )

        # Ensure total_expected matches plan after create_job
        job.total_expected = total_expected
        params = dict(job.search_parameters or {})
        params["limit"] = total_expected
        params["city_full"] = True
        params["coverage_plan"] = plan
        job.search_parameters = params
        await self.db.flush()

        started = False
        if auto_start:
            await self.start_job(job.id, user)
            started = True
            await self.db.refresh(job)

        return {
            "mode": "city_full",
            "city": city,
            "country_code": country_code,
            "category": category,
            "queries_planned": len(plan),
            "limit_per_query": limit_per,
            "total_expected": total_expected,
            "job_id": str(job.id),
            "job": {
                "id": str(job.id),
                "name": job.name,
                "status": job.status,
                "total_expected": job.total_expected,
            },
            "auto_started": started,
            "note": (
                "Single job runs district + keyword + geo-grid Places queries; "
                "dedupe merges by place_id. Capped by places_daily_quota."
            ),
        }

    async def create_job(
        self,
        payload: dict[str, Any],
        user: User,
        *,
        auto_start: bool = False,
    ) -> DiscoveryJob:
        provider_key = payload.get("provider") or "licensed_directory"
        keywords = payload.get("keywords") or []
        search_keyword = payload.get("search_keyword")
        search_keyword_ar = payload.get("search_keyword_ar")
        if not search_keyword:
            search_keyword, inferred_ar = _split_keywords(
                keywords,
                payload.get("language") or "both",
            )
            search_keyword_ar = search_keyword_ar or inferred_ar

        country, location, category_obj, provider_row = await self.resolve_references(
            country_code=payload.get("country_code") or "SA",
            city=payload.get("city"),
            category=payload.get("category"),
            country_id=payload.get("country_id"),
            location_id=payload.get("location_id"),
            category_id=payload.get("category_id"),
            provider_key=provider_key,
        )

        try:
            adapter = get_provider(
                "places_api"
                if provider_row.provider_type == "official_api"
                and "google" in provider_row.name.lower()
                else provider_row.provider_type
            )
        except KeyError:
            adapter = get_provider(provider_key)

        limit = int(payload.get("limit") or 100)
        extra_params = dict(payload.get("search_parameters") or {})
        is_city_full = bool(extra_params.get("city_full") or extra_params.get("coverage_plan"))
        purpose = "discovery"
        try:
            enforce_can_search(adapter, purpose=purpose)
            # City-full jobs are capped inside the provider by daily_quota × plan length
            quota_check = min(limit, adapter.get_data_policy().daily_quota) if is_city_full else limit
            adapter.validate_quota(max(quota_check, 1), used_today=0)
        except (SourcePolicyError, ValueError) as exc:
            raise DiscoveryError(str(exc), 400) from exc

        search_parameters = {
            "country_code": payload.get("country_code") or "SA",
            "city": payload.get("city") or (location.name if location else None),
            "category": payload.get("category")
            or (category_obj.slug if category_obj else None),
            "keywords": keywords,
            "language": payload.get("language") or "both",
            "limit": limit,
            "provider_key": adapter.key,
        }
        search_parameters.update(extra_params)
        search_parameters["limit"] = limit
        search_parameters["provider_key"] = adapter.key

        job = DiscoveryJob(
            id=uuid.uuid4(),
            name=payload["name"],
            country_id=country.id if country else None,
            location_id=location.id if location else None,
            category_id=category_obj.id if category_obj else None,
            provider_id=provider_row.id,
            search_keyword=search_keyword,
            search_keyword_ar=search_keyword_ar,
            search_parameters=search_parameters,
            status="pending",
            total_expected=limit,
            created_by=user.id,
        )
        self.db.add(job)
        await self.db.flush()

        if auto_start:
            await self.start_job(job.id, user)
            await self.db.refresh(job)
        return job

    async def start_job(self, job_id: UUID, user: User) -> DiscoveryJob:
        job = await self._get_job(job_id)
        if job.status in ACTIVE_STATUSES:
            raise DiscoveryError("Job is already running", 409)
        if job.status == "cancelled":
            raise DiscoveryError("Cancelled jobs cannot be started; retry instead", 400)

        job.status = "queued"
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = None
        await self.db.flush()
        # Commit before enqueue so workers (including eager mode) can see the job
        await self.db.commit()

        # Import lazily to avoid circular imports at module load
        from app.workers.discovery_tasks import run_discovery_job

        run_discovery_job.delay(str(job.id))
        await self.db.refresh(job)
        return job

    async def pause_job(self, job_id: UUID) -> DiscoveryJob:
        job = await self._get_job(job_id)
        if job.status not in ACTIVE_STATUSES:
            raise DiscoveryError("Only queued/processing jobs can be paused", 400)
        job.status = "pending"
        await self.db.flush()
        return job

    async def cancel_job(self, job_id: UUID) -> DiscoveryJob:
        job = await self._get_job(job_id)
        if job.status in TERMINAL_STATUSES and job.status != "failed":
            raise DiscoveryError("Job already finished", 400)
        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return job

    async def retry_job(self, job_id: UUID, user: User) -> DiscoveryJob:
        job = await self._get_job(job_id)
        if job.status not in {"failed", "cancelled", "partially_completed", "completed"}:
            raise DiscoveryError("Job is not in a retryable state", 400)
        job.total_processed = 0
        job.total_created = 0
        job.total_duplicates = 0
        job.total_failed = 0
        return await self.start_job(job.id, user)

    async def preview(
        self,
        payload: dict[str, Any],
        *,
        sample_records: Optional[list[dict[str, Any]]] = None,
    ) -> dict[str, Any]:
        provider_key = payload.get("provider") or "licensed_directory"
        keywords = payload.get("keywords") or []
        keyword, keyword_ar = _split_keywords(keywords, payload.get("language") or "both")
        limit = int(payload.get("limit") or 20)

        adapter = get_provider(
            provider_key,
            sample_mode=sample_records is not None,
            sample_records=sample_records,
        )
        purpose = "discovery"
        try:
            enforce_can_search(adapter, purpose=purpose)
            adapter.validate_quota(limit, used_today=0)
        except (SourcePolicyError, ValueError) as exc:
            raise DiscoveryError(str(exc), 400) from exc

        query = ProviderSearchQuery(
            keyword=keyword,
            keyword_ar=keyword_ar,
            country_code=payload.get("country_code") or "SA",
            city=payload.get("city"),
            category=payload.get("category"),
            language=payload.get("language") or "both",
            limit=limit,
        )
        records = await adapter.search(query)
        previews = [preview_safe_record(adapter, r) for r in records]
        return {
            "provider": adapter.key,
            "policy": adapter.get_data_policy().notes,
            "count": len(previews),
            "results": previews,
        }

    async def list_jobs(
        self,
        *,
        page: int = 1,
        limit: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[DiscoveryJob], int]:
        stmt = select(DiscoveryJob)
        count_stmt = select(func.count()).select_from(DiscoveryJob)
        if status:
            stmt = stmt.where(DiscoveryJob.status == status)
            count_stmt = count_stmt.where(DiscoveryJob.status == status)
        total = (await self.db.execute(count_stmt)).scalar_one()
        result = await self.db.execute(
            stmt.order_by(DiscoveryJob.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_job(self, job_id: UUID) -> DiscoveryJob:
        return await self._get_job(job_id)

    async def job_results(self, job_id: UUID, *, page: int = 1, limit: int = 20):
        job = await self._get_job(job_id)
        # Businesses linked via lead_sources collected around this job window is complex;
        # return businesses matching location/category created since job start as a practical view.
        stmt = select(Business)
        if job.location_id:
            stmt = stmt.where(Business.location_id == job.location_id)
        if job.category_id:
            stmt = stmt.where(Business.category_id == job.category_id)
        if job.started_at:
            stmt = stmt.where(Business.created_at >= job.started_at)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()
        rows = await self.db.execute(
            stmt.order_by(Business.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        return list(rows.scalars().all()), total, job

    async def _get_job(self, job_id: UUID) -> DiscoveryJob:
        job = await self.db.get(DiscoveryJob, job_id)
        if job is None:
            raise DiscoveryError("Discovery job not found", 404)
        return job


def or_slug_or_name(category: str):
    from sqlalchemy import or_

    slug = category.lower().replace(" ", "-")
    return or_(
        BusinessCategory.slug == slug,
        func.lower(BusinessCategory.name) == category.lower(),
    )


class DiscoveryExecutionService:
    """Sync execution used by Celery workers."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.dedupe = DeduplicationService(session)

    def execute_job(self, job_id: UUID) -> dict[str, Any]:
        job = self.session.get(DiscoveryJob, job_id)
        if job is None:
            raise DiscoveryError("Job not found", 404)
        if job.status == "cancelled":
            return {"status": "cancelled"}
        if job.status == "pending":
            # paused
            return {"status": "pending"}

        job.status = "processing"
        self.session.flush()

        provider_row = self.session.get(DataProvider, job.provider_id) if job.provider_id else None
        params = job.search_parameters or {}
        provider_key = params.get("provider_key") or (
            provider_row.provider_type if provider_row else "licensed_directory"
        )
        if provider_row and provider_row.provider_type == "official_api":
            provider_key = "places_api"

        adapter = get_provider(provider_key)
        limit = int(params.get("limit") or job.total_expected or 100)

        extra: dict[str, Any] = {}
        coverage_plan = params.get("coverage_plan")
        if params.get("city_full") and not coverage_plan:
            coverage_plan = build_city_coverage_plan(
                city=params.get("city") or "Riyadh",
                country_code=params.get("country_code") or "SA",
                category=params.get("category") or "all",
                latitude=params.get("latitude"),
                longitude=params.get("longitude"),
                max_queries=int(params.get("max_queries") or 180),
                limit_per_query=int(params.get("limit_per_query") or 60),
                grid=int(params.get("grid") or 7),
                keywords=params.get("keywords") if isinstance(params.get("keywords"), list) else None,
            )
        if coverage_plan:
            extra["coverage_plan"] = coverage_plan
            # Allow the fan-out to collect up to plan × per-query (deduped)
            limit = max(
                limit,
                len(coverage_plan) * int(params.get("limit_per_query") or 60),
            )
            job.total_expected = limit
            self.session.flush()

        query = ProviderSearchQuery(
            keyword=job.search_keyword,
            keyword_ar=job.search_keyword_ar,
            country_code=params.get("country_code") or "SA",
            city=params.get("city"),
            category=params.get("category"),
            language=params.get("language") or "both",
            limit=limit,
            extra=extra,
        )

        try:
            records = _run_async(adapter.search(query))
        except Exception as exc:
            logger.exception("Discovery provider search failed")
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
            job.total_failed = (job.total_failed or 0) + 1
            self.session.flush()
            raise DiscoveryError(f"Provider search failed: {exc}", 502) from exc

        created = 0
        duplicates = 0
        failed = 0
        processed = 0

        for record in records:
            if job.status == "cancelled":
                break
            # Re-read pause/cancel signals
            self.session.refresh(job)
            if job.status in {"pending", "cancelled"}:
                break

            processed += 1
            try:
                outcome = self._persist_record(job, adapter, provider_row, record)
                if outcome == "created":
                    created += 1
                elif outcome == "duplicate":
                    duplicates += 1
                elif outcome == "skipped_policy":
                    duplicates += 1  # counted as non-create
            except Exception:
                logger.exception("Failed to persist discovery record")
                failed += 1

            job.total_processed = processed
            job.total_created = created
            job.total_duplicates = duplicates
            job.total_failed = failed
            self.session.flush()

        self.session.refresh(job)
        if job.status == "cancelled":
            pass
        elif job.status == "pending":
            pass
        elif failed and created:
            job.status = "partially_completed"
            job.completed_at = datetime.now(timezone.utc)
        elif failed and not created:
            job.status = "failed"
            job.completed_at = datetime.now(timezone.utc)
        else:
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)

        job.total_processed = processed
        job.total_created = created
        job.total_duplicates = duplicates
        job.total_failed = failed
        self.session.flush()
        return {
            "status": job.status,
            "processed": processed,
            "created": created,
            "duplicates": duplicates,
            "failed": failed,
        }

    def _persist_record(
        self,
        job: DiscoveryJob,
        adapter: BusinessProvider,
        provider_row: Optional[DataProvider],
        record: ProviderBusinessRecord,
    ) -> str:
        policy = adapter.get_data_policy()

        if not policy.persist_crm_fields:
            return "skipped_policy"

        try:
            payload = build_persistable_payload(adapter, record)
        except SourcePolicyError:
            return "skipped_policy"

        match = self.dedupe.find_duplicate_sync(
            external_id=payload.get("external_id"),
            provider_id=provider_row.id if provider_row else None,
            website_url=payload.get("website_url"),
            phone=payload.get("phone"),
            business_name=payload.get("business_name") or payload.get("business_name_ar"),
            location_id=job.location_id,
        )

        if match:
            business = match.business
            # Merge fresher Places contact/website onto existing stub
            if not business.website_url and payload.get("website_url"):
                business.website_url = payload["website_url"]
            if not business.address and payload.get("address"):
                business.address = payload["address"]
            if not business.district and payload.get("district"):
                business.district = payload["district"]
            if business.latitude is None and payload.get("latitude") is not None:
                business.latitude = payload["latitude"]
            if business.longitude is None and payload.get("longitude") is not None:
                business.longitude = payload["longitude"]
            if provider_row:
                self._add_provenance(business, job, adapter, provider_row, record, payload)
                self._merge_contacts(business, provider_row, record, payload)
            self.session.add(
                Activity(
                    id=uuid.uuid4(),
                    business_id=business.id,
                    user_id=job.created_by,
                    activity_type="lead_discovered",
                    description=f"Duplicate matched via {match.strategy}",
                    metadata_={
                        "discovery_job_id": str(job.id),
                        "dedupe_strategy": match.strategy,
                        "provider": adapter.key,
                    },
                )
            )
            self.session.flush()
            if business.website_url:
                self._queue_enrichment(business.id)
            self._queue_score(business.id)
            return "duplicate"

        name = payload.get("business_name") or payload.get("business_name_ar")
        # Places candidates start in researching; licensed/manual start as new
        initial_status = "researching" if adapter.key == "places_api" else "new"
        business = Business(
            id=uuid.uuid4(),
            business_name=name,
            business_name_ar=payload.get("business_name_ar"),
            normalized_name=normalize_business_name(name),
            category_id=job.category_id,
            location_id=job.location_id,
            address=payload.get("address"),
            district=payload.get("district"),
            website_url=payload.get("website_url"),
            description=payload.get("description"),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            business_status="unknown",
            lead_status=initial_status,
            first_discovered_at=datetime.now(timezone.utc),
            qualification_reason={
                "source": adapter.key,
                "place_id": payload.get("external_id"),
                "has_website": bool(payload.get("website_url")),
                "has_phone": bool(payload.get("phone")),
                "category_hint": payload.get("category") or record.category,
                "monetization": _monetization_packs(
                    has_website=bool(payload.get("website_url")),
                    category=payload.get("category") or record.category,
                ),
            },
        )
        self.session.add(business)
        self.session.flush()

        if provider_row:
            source = self._add_provenance(business, job, adapter, provider_row, record, payload)
            self._merge_contacts(business, provider_row, record, payload, source_id=source.id)

        self.session.add(
            Activity(
                id=uuid.uuid4(),
                business_id=business.id,
                user_id=job.created_by,
                activity_type="lead_discovered",
                description="Business discovered",
                metadata_={
                    "discovery_job_id": str(job.id),
                    "provider": adapter.key,
                    "place_id": payload.get("external_id"),
                    "has_website": bool(business.website_url),
                },
            )
        )

        if business.website_url:
            self._queue_enrichment(business.id)
        self._queue_score(business.id)
        return "created"

    def _queue_enrichment(self, business_id: UUID) -> None:
        """Create enrichment job and schedule Celery after flush (caller commits)."""
        existing = (
            self.session.execute(
                select(EnrichmentJob).where(
                    EnrichmentJob.business_id == business_id,
                    EnrichmentJob.job_type == "website_discovery",
                    EnrichmentJob.status.in_(["pending", "queued", "processing"]),
                )
            )
            .scalars()
            .first()
        )
        if existing:
            return
        job = EnrichmentJob(
            id=uuid.uuid4(),
            business_id=business_id,
            job_type="website_discovery",
            status="queued",
            scheduled_at=datetime.now(timezone.utc),
        )
        self.session.add(job)
        self.session.flush()
        # Defer Celery until after DB commit via session info bag
        pending = self.session.info.setdefault("pending_enrichment_ids", [])
        pending.append(str(job.id))

    def _queue_score(self, business_id: UUID) -> None:
        pending = self.session.info.setdefault("pending_score_ids", [])
        pending.append(str(business_id))

    def _add_provenance(
        self,
        business: Business,
        job: DiscoveryJob,
        adapter: BusinessProvider,
        provider_row: DataProvider,
        record: ProviderBusinessRecord,
        payload: dict[str, Any],
    ) -> LeadSource:
        policy = adapter.get_data_policy()
        source = LeadSource(
            id=uuid.uuid4(),
            business_id=business.id,
            provider_id=provider_row.id,
            source_type=adapter.key,
            source_url=payload.get("source_url") or record.source_url,
            external_reference=payload.get("external_id") or record.external_id,
            collection_method="api_search",
            policy_version=provider_row.policy_reference,
            permitted_purposes=policy.permitted_purposes,
            retention_expires_at=retention_expires_at(policy),
            metadata_={
                "discovery_job_id": str(job.id),
                "provider_key": adapter.key,
            },
        )
        self.session.add(source)
        self.session.flush()
        return source

    def _merge_contacts(
        self,
        business: Business,
        provider_row: DataProvider,
        record: ProviderBusinessRecord,
        payload: dict[str, Any],
        source_id: Optional[UUID] = None,
    ) -> None:
        # Public business contacts are NOT consented for marketing by default
        phone = payload.get("phone") or record.phone
        email = payload.get("email") or record.email
        if phone:
            normalized = normalize_phone(phone)
            exists = self.session.execute(
                select(BusinessContact).where(
                    BusinessContact.business_id == business.id,
                    BusinessContact.contact_type == "business_phone",
                    BusinessContact.normalized_value == normalized,
                )
            ).scalar_one_or_none()
            if not exists and normalized:
                self.session.add(
                    BusinessContact(
                        id=uuid.uuid4(),
                        business_id=business.id,
                        contact_type="business_phone",
                        contact_value=phone,
                        normalized_value=normalized,
                        is_primary=True,
                        is_verified=False,
                        source_id=source_id,
                    )
                )
        if email:
            normalized = normalize_email(email)
            exists = self.session.execute(
                select(BusinessContact).where(
                    BusinessContact.business_id == business.id,
                    BusinessContact.contact_type == "business_email",
                    BusinessContact.normalized_value == normalized,
                )
            ).scalar_one_or_none()
            if not exists and normalized:
                self.session.add(
                    BusinessContact(
                        id=uuid.uuid4(),
                        business_id=business.id,
                        contact_type="business_email",
                        contact_value=email,
                        normalized_value=normalized,
                        is_primary=True,
                        is_verified=False,
                        source_id=source_id,
                    )
                )
