"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    businesses,
    campaigns,
    categories,
    consent,
    contacts,
    discovery,
    enrichment,
    jobs,
    locations,
    outreach,
    providers,
    scoring,
    settings,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(locations.router)
api_router.include_router(categories.router)
api_router.include_router(providers.router)
api_router.include_router(discovery.router)
api_router.include_router(jobs.router)
api_router.include_router(businesses.router)
api_router.include_router(contacts.router)
api_router.include_router(enrichment.router)
api_router.include_router(scoring.router)
api_router.include_router(consent.router)
api_router.include_router(campaigns.router)
api_router.include_router(settings.router)
api_router.include_router(outreach.router)
