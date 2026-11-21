"""Location read endpoints (foundation)."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.location import Country, Location
from app.utils.pagination import success_response

router = APIRouter(prefix="/locations", tags=["Locations"])


@router.get("/countries")
async def list_countries(db: DbSession, _user: CurrentUser):
    result = await db.execute(
        select(Country).where(Country.is_active.is_(True)).order_by(Country.name)
    )
    countries = result.scalars().all()
    data = [
        {
            "id": str(c.id),
            "name": c.name,
            "name_ar": c.name_ar,
            "iso_code": c.iso_code,
            "phone_code": c.phone_code,
        }
        for c in countries
    ]
    return success_response(data=data, message="Countries retrieved")


@router.get("/regions")
async def list_regions(
    db: DbSession,
    _user: CurrentUser,
    country_id: Optional[UUID] = None,
):
    return await _list_by_type(db, "region", country_id)


@router.get("/cities")
async def list_cities(
    db: DbSession,
    _user: CurrentUser,
    country_id: Optional[UUID] = None,
    parent_id: Optional[UUID] = None,
):
    return await _list_by_type(db, "city", country_id, parent_id)


@router.get("/districts")
async def list_districts(
    db: DbSession,
    _user: CurrentUser,
    country_id: Optional[UUID] = None,
    parent_id: Optional[UUID] = None,
):
    return await _list_by_type(db, "district", country_id, parent_id)


async def _list_by_type(
    db: DbSession,
    location_type: str,
    country_id: Optional[UUID] = None,
    parent_id: Optional[UUID] = None,
):
    stmt = select(Location).where(
        Location.is_active.is_(True),
        Location.location_type == location_type,
    )
    if country_id:
        stmt = stmt.where(Location.country_id == country_id)
    if parent_id:
        stmt = stmt.where(Location.parent_id == parent_id)
    stmt = stmt.order_by(Location.name)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    data = [
        {
            "id": str(loc.id),
            "country_id": str(loc.country_id),
            "parent_id": str(loc.parent_id) if loc.parent_id else None,
            "name": loc.name,
            "name_ar": loc.name_ar,
            "slug": loc.slug,
            "location_type": loc.location_type,
            "latitude": float(loc.latitude) if loc.latitude is not None else None,
            "longitude": float(loc.longitude) if loc.longitude is not None else None,
        }
        for loc in rows
    ]
    return success_response(data=data, message=f"{location_type.title()}s retrieved")
