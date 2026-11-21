"""Google Places API adapter — paid Text Search / Details → candidate CRM leads."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.providers.base import (
    BusinessProvider,
    ProviderBusinessRecord,
    ProviderDataPolicy,
    ProviderSearchQuery,
)

logger = logging.getLogger(__name__)

# Text Search field mask — must include nextPageToken for pagination
SEARCH_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.addressComponents",
        "places.location",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.types",
        "places.primaryType",
        "places.primaryTypeDisplayName",
        "places.googleMapsUri",
        "nextPageToken",
    ]
)

# City center bias (fallback when no per-query location_bias is supplied)
CITY_BIAS: dict[str, dict[str, float]] = {
    "riyadh": {"lat": 24.7136, "lng": 46.6753, "radius_m": 35000},
    "jeddah": {"lat": 21.4858, "lng": 39.1925, "radius_m": 30000},
    "dammam": {"lat": 26.4207, "lng": 50.0888, "radius_m": 25000},
    "mecca": {"lat": 21.3891, "lng": 39.8579, "radius_m": 20000},
    "medina": {"lat": 24.5247, "lng": 39.5692, "radius_m": 20000},
    "khobar": {"lat": 26.2172, "lng": 50.1971, "radius_m": 18000},
    "dubai": {"lat": 25.2048, "lng": 55.2708, "radius_m": 40000},
}

DETAILS_FIELD_MASK = ",".join(
    [
        "id",
        "displayName",
        "formattedAddress",
        "addressComponents",
        "location",
        "nationalPhoneNumber",
        "internationalPhoneNumber",
        "websiteUri",
        "types",
        "primaryType",
        "primaryTypeDisplayName",
        "googleMapsUri",
    ]
)

# Map common Google primaryType → our category slugs when possible
TYPE_TO_SLUG = {
    "restaurant": "restaurants",
    "cafe": "cafes",
    "bakery": "bakeries",
    "meal_takeaway": "restaurants",
    "meal_delivery": "restaurants",
    "grocery_or_supermarket": "grocery-stores",
    "supermarket": "supermarkets",
    "pharmacy": "pharmacies",
    "florist": "flower-shops",
    "real_estate_agency": "real-estate",
}


class PlacesApiProvider(BusinessProvider):
    """Paid Google Places usage for merchant candidate discovery.

    Creates SoouqLive directory candidates with place_id provenance.
    Email is not provided by Places — use website enrichment.
    """

    key = "places_api"
    display_name = "Google Places API"

    def __init__(
        self,
        api_key: Optional[str] = None,
        sample_records: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.google_maps_api_key
        self._sample_records = sample_records
        self.daily_quota = settings.places_daily_quota

    def get_data_policy(self) -> ProviderDataPolicy:
        return ProviderDataPolicy(
            provider_key=self.key,
            provider_type="official_api",
            persist_crm_fields=True,
            place_id_allowed=True,
            restricted_fields=set(),
            permitted_fields={
                "external_id",
                "business_name",
                "business_name_ar",
                "address",
                "district",
                "city",
                "website_url",
                "phone",
                "latitude",
                "longitude",
                "category",
                "description",
                "source_url",
            },
            permitted_purposes=["discovery", "discovery_preview", "maps_display"],
            retention_days=365,
            daily_quota=self.daily_quota,
            rate_limit_per_minute=60,
            attribution_required=True,
            preview_only_restricted=False,
            notes=(
                "Paid Places API candidates for SoouqLive sales directory. "
                "Store place_id as external_id. Email is not returned by Places — "
                "run website enrichment. Google attribution required in UI when shown."
            ),
        )

    def can_persist(self, field_name: str) -> bool:
        return field_name in self.get_data_policy().permitted_fields

    async def search(self, query: ProviderSearchQuery) -> list[ProviderBusinessRecord]:
        plan = query.extra.get("coverage_plan") if query.extra else None
        if plan:
            return await self._search_coverage(query, plan)

        # Soft cap: single-query jobs rarely need more than daily_quota
        self.validate_quota(min(query.limit, self.daily_quota))
        if self._sample_records is not None:
            return [self._map_item(item) for item in self._sample_records[: query.limit]]

        if not self.api_key:
            return []

        text_query = query.keyword
        if query.category and query.category.lower() not in (query.keyword or "").lower():
            text_query = f"{query.keyword} {query.category}".strip()
        if query.city:
            text_query = f"{text_query} in {query.city}"

        location_bias = (query.extra or {}).get("location_bias")
        return await self._search_text(
            text_query=text_query,
            country_code=query.country_code or "SA",
            language=query.language or "en",
            limit=query.limit,
            included_type=self._included_type(query),
            location_bias=location_bias,
            city=query.city,
        )

    async def _search_coverage(
        self,
        query: ProviderSearchQuery,
        plan: list[dict[str, Any]],
    ) -> list[ProviderBusinessRecord]:
        """Fan out many Text Search queries (districts + keywords + geo grid)."""
        if self._sample_records is not None:
            return [self._map_item(item) for item in self._sample_records[: query.limit]]
        if not self.api_key:
            return []

        # Cap plan length by remaining daily quota (≈1 request unit per page ≈20 results)
        per = max(int((plan[0] or {}).get("limit") or 60), 1) if plan else 60
        max_plan = max(1, min(len(plan), self.daily_quota // max(per // 20, 1)))
        plan = plan[:max_plan]

        seen_ids: set[str] = set()
        records: list[ProviderBusinessRecord] = []
        overall_target = max(query.limit, 1)

        for idx, spec in enumerate(plan):
            if len(records) >= overall_target:
                break
            text = spec.get("text") or spec.get("keyword") or query.keyword
            sub_limit = int(spec.get("limit") or per)
            remaining = overall_target - len(records)
            sub_limit = min(sub_limit, remaining)
            bias = spec.get("location_bias")
            country = spec.get("country_code") or query.country_code or "SA"

            logger.info(
                "Places coverage %s/%s: %s (limit=%s bias=%s)",
                idx + 1,
                len(plan),
                text,
                sub_limit,
                bool(bias),
            )
            try:
                batch = await self._search_text(
                    text_query=text,
                    country_code=country,
                    language=query.language or "en",
                    limit=sub_limit,
                    included_type=None,  # broad coverage — don't restrict type
                    location_bias=bias,
                    city=query.city,
                )
            except Exception:
                logger.exception("Coverage subquery failed: %s", text)
                continue

            for rec in batch:
                ext = rec.external_id or ""
                if ext and ext in seen_ids:
                    continue
                if ext:
                    seen_ids.add(ext)
                records.append(rec)
                if len(records) >= overall_target:
                    break

            # Gentle pacing between sub-queries (rate_limit_per_minute ~60)
            await asyncio.sleep(1.0)

        logger.info(
            "Places coverage done: %s unique / target %s across %s queries",
            len(records),
            overall_target,
            len(plan),
        )
        return records[:overall_target]

    async def _search_text(
        self,
        *,
        text_query: str,
        country_code: str,
        language: str,
        limit: int,
        included_type: Optional[str] = None,
        location_bias: Optional[dict[str, Any]] = None,
        city: Optional[str] = None,
    ) -> list[ProviderBusinessRecord]:
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": SEARCH_FIELD_MASK,
        }

        # Base body stays identical across pages (Google requires this for pageToken)
        base_body: dict[str, Any] = {
            "textQuery": text_query,
            "pageSize": 20,
            "languageCode": "ar" if language == "ar" else "en",
            "regionCode": country_code or "SA",
        }
        if included_type:
            base_body["includedType"] = included_type
            base_body["strictTypeFiltering"] = False

        bias = location_bias
        if not bias and city:
            known = CITY_BIAS.get(city.strip().lower())
            if known:
                bias = known
        if bias:
            radius = float(bias.get("radius_m") or bias.get("radius") or 30000)
            radius = min(max(radius, 500.0), 50000.0)
            base_body["locationBias"] = {
                "circle": {
                    "center": {
                        "latitude": float(bias["lat"]),
                        "longitude": float(bias["lng"]),
                    },
                    "radius": radius,
                }
            }

        target = max(limit, 1)
        seen_ids: set[str] = set()
        records: list[ProviderBusinessRecord] = []
        page_token: Optional[str] = None
        max_pages = max(1, min(50, (target + 19) // 20))

        async with httpx.AsyncClient(timeout=45.0) as client:
            for page_idx in range(max_pages):
                body = dict(base_body)
                if page_token:
                    body["pageToken"] = page_token

                response = await client.post(
                    "https://places.googleapis.com/v1/places:searchText",
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()

                page_places = payload.get("places") or []
                if not page_places:
                    break

                for place in page_places:
                    mapped = self._map_item(self._normalize_place(place))
                    ext = mapped.external_id or ""
                    if ext and ext in seen_ids:
                        continue
                    if ext:
                        seen_ids.add(ext)
                    records.append(mapped)
                    if len(records) >= target:
                        break

                logger.info(
                    "Places page %s: got %s raw, unique total %s / target %s",
                    page_idx + 1,
                    len(page_places),
                    len(records),
                    target,
                )

                if len(records) >= target:
                    break

                page_token = payload.get("nextPageToken") or None
                if not page_token:
                    break
                await asyncio.sleep(2.0)

        records = records[:target]

        if get_settings().places_fetch_details:
            filled: list[ProviderBusinessRecord] = []
            for rec in records:
                if rec.external_id and (not rec.website_url or not rec.phone):
                    detailed = await self.get_details(rec.external_id)
                    filled.append(detailed or rec)
                else:
                    filled.append(rec)
            return filled
        return records

    def _included_type(self, query: ProviderSearchQuery) -> Optional[str]:
        cat = (query.category or query.keyword or "").lower()
        if "restaurant" in cat or cat in {"restaurants", "food"}:
            return "restaurant"
        if "cafe" in cat or cat == "cafes":
            return "cafe"
        if "bakery" in cat or cat == "bakeries":
            return "bakery"
        if "real" in cat and "estate" in cat:
            return "real_estate_agency"
        return None

    async def get_details(self, provider_id: str) -> Optional[ProviderBusinessRecord]:
        if self._sample_records is not None:
            for item in self._sample_records:
                if item.get("place_id") == provider_id or item.get("id") == provider_id:
                    return self._map_item(item)
            return None

        if not self.api_key:
            return None

        place_path = provider_id
        if not place_path.startswith("places/"):
            place_path = f"places/{provider_id}"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": DETAILS_FIELD_MASK,
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.get(
                f"https://places.googleapis.com/v1/{place_path}",
                headers=headers,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return self._map_item(self._normalize_place(response.json()))

    def _normalize_place(self, place: dict[str, Any]) -> dict[str, Any]:
        place_id = place.get("id") or place.get("place_id")
        if isinstance(place_id, str) and place_id.startswith("places/"):
            place_id = place_id.split("/", 1)[1]

        display = place.get("displayName") or {}
        name = display.get("text") if isinstance(display, dict) else display
        primary = place.get("primaryType") or ""
        primary_display = place.get("primaryTypeDisplayName") or {}
        primary_label = (
            primary_display.get("text")
            if isinstance(primary_display, dict)
            else primary_display
        )
        category = TYPE_TO_SLUG.get(primary) or primary or primary_label

        loc = place.get("location") or {}
        lat = loc.get("latitude")
        lng = loc.get("longitude")

        district = None
        city = None
        for comp in place.get("addressComponents") or []:
            types = comp.get("types") or []
            text = comp.get("longText") or comp.get("shortText")
            if "sublocality" in types or "neighborhood" in types:
                district = text or district
            if "locality" in types:
                city = text or city

        phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
        website = place.get("websiteUri") or place.get("website_url")
        maps_uri = place.get("googleMapsUri")

        return {
            "place_id": place_id,
            "business_name": name or place.get("business_name"),
            "address": place.get("formattedAddress") or place.get("address"),
            "district": district or place.get("district"),
            "city": city or place.get("city"),
            "phone": phone or place.get("phone"),
            "website_url": website,
            "latitude": lat if lat is not None else place.get("latitude"),
            "longitude": lng if lng is not None else place.get("longitude"),
            "category": category or place.get("category"),
            "source_url": maps_uri or place.get("source_url"),
            "types": place.get("types") or [],
            "primary_type": primary,
        }

    def _map_item(self, item: dict[str, Any]) -> ProviderBusinessRecord:
        lat = item.get("latitude")
        lng = item.get("longitude")
        return ProviderBusinessRecord(
            external_id=str(item.get("place_id") or item.get("id") or "") or None,
            business_name=item.get("business_name") or item.get("name"),
            address=item.get("address"),
            district=item.get("district"),
            city=item.get("city"),
            website_url=item.get("website_url"),
            phone=item.get("phone"),
            latitude=float(lat) if lat is not None else None,
            longitude=float(lng) if lng is not None else None,
            category=item.get("category"),
            source_url=item.get("source_url"),
            raw=item,
        )
