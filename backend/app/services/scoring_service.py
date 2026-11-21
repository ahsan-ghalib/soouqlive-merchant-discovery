"""Configurable merchant lead qualification scoring."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.business import Business
from app.models.category import BusinessCategory
from app.models.contact import BusinessContact
from app.utils.normalization import normalize_domain

logger = logging.getLogger(__name__)

# Merchant categories that fit SoouqLive delivery marketplace well
DEFAULT_RELEVANT_CATEGORY_SLUGS = {
    "restaurants",
    "cafes",
    "bakeries",
    "grocery-stores",
    "supermarkets",
    "dessert-shops",
    "flower-shops",
    "pharmacies",
}

# Stronger fit subset (core delivery verticals)
DEFAULT_STRONG_FIT_SLUGS = {
    "restaurants",
    "cafes",
    "bakeries",
    "grocery-stores",
    "supermarkets",
    "dessert-shops",
}

DEFAULT_WEIGHTS = {
    "relevant_category": 25,
    "active_website": 15,
    "verified_public_contact": 15,
    "relevant_delivery_service": 15,
    "strong_soouqlive_fit": 15,
    # Sales opportunity: no website = pitch site/portal (separate from marketplace fit)
    "website_gap_opportunity": 15,
}


@dataclass
class ScoreBreakdown:
    total: int
    components: dict[str, int] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def to_qualification_reason(self) -> dict[str, Any]:
        return {
            "score": self.total,
            "components": self.components,
            "details": self.details,
            "scored_at": datetime.now(timezone.utc).isoformat(),
            "version": "v1",
            "note": "Consent is not a scoring factor; it is a separate eligibility condition.",
        }


class ScoringService:
    def __init__(
        self,
        session: AsyncSession | Session,
        *,
        weights: Optional[dict[str, int]] = None,
        relevant_slugs: Optional[set[str]] = None,
        strong_fit_slugs: Optional[set[str]] = None,
    ) -> None:
        self.session = session
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self.relevant_slugs = relevant_slugs or DEFAULT_RELEVANT_CATEGORY_SLUGS
        self.strong_fit_slugs = strong_fit_slugs or DEFAULT_STRONG_FIT_SLUGS

    async def score_business_async(
        self,
        business_id: UUID,
        *,
        user_id: Optional[UUID] = None,
        auto_qualify: bool = False,
        qualify_threshold: int = 60,
    ) -> ScoreBreakdown:
        assert isinstance(self.session, AsyncSession)
        business = await self.session.get(Business, business_id)
        if business is None:
            raise ValueError("Business not found")

        contacts = list(
            (
                await self.session.execute(
                    select(BusinessContact).where(BusinessContact.business_id == business_id)
                )
            )
            .scalars()
            .all()
        )
        category = None
        if business.category_id:
            category = await self.session.get(BusinessCategory, business.category_id)

        breakdown = self._compute(business, contacts, category)
        business.qualification_score = breakdown.total
        business.qualification_reason = breakdown.to_qualification_reason()

        if auto_qualify and breakdown.total >= qualify_threshold and business.lead_status == "new":
            business.lead_status = "qualified"

        self.session.add(
            Activity(
                id=uuid4(),
                business_id=business.id,
                user_id=user_id,
                activity_type="lead_qualified" if business.lead_status == "qualified" else "lead_discovered",
                description="Lead score calculated",
                metadata_=breakdown.to_qualification_reason(),
            )
        )
        await self.session.flush()
        return breakdown

    def score_business_sync(
        self,
        business_id: UUID,
        *,
        user_id: Optional[UUID] = None,
        auto_qualify: bool = False,
        qualify_threshold: int = 60,
    ) -> ScoreBreakdown:
        assert isinstance(self.session, Session)
        business = self.session.get(Business, business_id)
        if business is None:
            raise ValueError("Business not found")

        contacts = list(
            self.session.execute(
                select(BusinessContact).where(BusinessContact.business_id == business_id)
            )
            .scalars()
            .all()
        )
        category = (
            self.session.get(BusinessCategory, business.category_id)
            if business.category_id
            else None
        )
        breakdown = self._compute(business, contacts, category)
        business.qualification_score = breakdown.total
        business.qualification_reason = breakdown.to_qualification_reason()

        if auto_qualify and breakdown.total >= qualify_threshold and business.lead_status in {
            "new",
            "researching",
        }:
            business.lead_status = "qualified"

        self.session.add(
            Activity(
                id=uuid4(),
                business_id=business.id,
                user_id=user_id,
                activity_type="lead_qualified"
                if business.lead_status == "qualified"
                else "lead_discovered",
                description="Lead score calculated",
                metadata_=breakdown.to_qualification_reason(),
            )
        )
        self.session.flush()
        return breakdown

    def _compute(
        self,
        business: Business,
        contacts: list[BusinessContact],
        category: Optional[BusinessCategory],
    ) -> ScoreBreakdown:
        components: dict[str, int] = {
            "relevant_category": 0,
            "active_website": 0,
            "verified_public_contact": 0,
            "relevant_delivery_service": 0,
            "strong_soouqlive_fit": 0,
            "website_gap_opportunity": 0,
        }
        details: dict[str, Any] = {}

        slug = (category.slug if category else None) or ""
        details["category_slug"] = slug or None

        if slug in self.relevant_slugs:
            components["relevant_category"] = self.weights["relevant_category"]

        domain = normalize_domain(business.website_url)
        has_website = bool(domain)
        if has_website:
            components["active_website"] = self.weights["active_website"]
            details["website_domain"] = domain
        else:
            details["website_domain"] = None
            components["website_gap_opportunity"] = self.weights["website_gap_opportunity"]

        has_email = any(c.contact_type == "business_email" for c in contacts)
        has_phone = any(c.contact_type == "business_phone" for c in contacts)
        details["has_website"] = has_website
        details["has_email"] = has_email
        details["has_phone"] = has_phone

        packs: list[str] = []
        if not has_website:
            packs.append("no_website_site_build")
        else:
            packs.append("website_upgrade")
        if slug in {"restaurants", "cafes", "bakeries", "dessert-shops"} or "restaurant" in slug:
            packs.append("restaurant_portal")
        if "real-estate" in slug or "real_estate" in slug:
            packs.append("real_estate_portal")
        if has_website and not has_email:
            packs.append("needs_email_enrichment")
        details["monetization_packs"] = packs

        has_verified_contact = any(
            c.is_verified
            and c.contact_type in {"business_email", "business_phone"}
            for c in contacts
        )
        has_any_public_contact = any(
            c.contact_type in {"business_email", "business_phone"} for c in contacts
        )
        if has_verified_contact:
            components["verified_public_contact"] = self.weights["verified_public_contact"]
            details["contact_quality"] = "verified"
        elif has_any_public_contact:
            components["verified_public_contact"] = self.weights["verified_public_contact"] // 2
            details["contact_quality"] = "public_unverified"
        else:
            details["contact_quality"] = "none"

        delivery_ready = slug in self.relevant_slugs and has_website and has_any_public_contact
        if delivery_ready:
            components["relevant_delivery_service"] = self.weights["relevant_delivery_service"]
        details["delivery_ready"] = delivery_ready

        if slug in self.strong_fit_slugs:
            components["strong_soouqlive_fit"] = self.weights["strong_soouqlive_fit"]

        total = min(100, sum(components.values()))
        return ScoreBreakdown(total=total, components=components, details=details)
