"""Website enrichment, SSRF, and extraction tests."""

from __future__ import annotations

import uuid
from unittest.mock import patch

import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enrichment.crawler import WebsiteCrawler
from app.enrichment.email_extractor import extract_emails
from app.enrichment.phone_extractor import extract_phones
from app.enrichment.social_extractor import extract_social_profiles
from app.enrichment.ssrf import SSRFError, validate_public_http_url
from app.enrichment.structured_data import extract_json_ld_business
from app.models.business import Business
from app.models.contact import BusinessContact
from app.models.source import DataProvider
from app.core.sync_database import SyncSessionLocal
from app.services.enrichment_service import EnrichmentExecutionService


HOME_HTML = """
<html><head>
<script type="application/ld+json">
{
  "@type": "LocalBusiness",
  "name": "Riyadh Flowers",
  "telephone": "+966501234567",
  "email": "hello@riyadhflowers.example",
  "sameAs": ["https://instagram.com/riyadhflowers"]
}
</script>
</head>
<body>
  <a href="/contact">Contact Us</a>
  <a href="mailto:sales@riyadhflowers.example">Email</a>
  <a href="tel:+966509998877">Call</a>
  <a href="https://facebook.com/riyadhflowers">FB</a>
</body></html>
"""

CONTACT_HTML = """
<html><body>
  <p>Reach us at support@riyadhflowers.example or 0501112233</p>
  <a href="https://twitter.com/riyadhflowers">Twitter</a>
</body></html>
"""

ROBOTS_TXT = "User-agent: *\nAllow: /\n"


def _mock_transport(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if url.endswith("/robots.txt"):
        return httpx.Response(200, text=ROBOTS_TXT)
    if "/contact" in url:
        return httpx.Response(200, text=CONTACT_HTML, headers={"content-type": "text/html"})
    return httpx.Response(200, text=HOME_HTML, headers={"content-type": "text/html"})


def test_ssrf_blocks_localhost_and_private_ips():
    with pytest.raises(SSRFError):
        validate_public_http_url("http://localhost/admin")
    with pytest.raises(SSRFError):
        validate_public_http_url("http://127.0.0.1/")
    with pytest.raises(SSRFError):
        validate_public_http_url("http://192.168.1.10/secret")
    with pytest.raises(SSRFError):
        validate_public_http_url("ftp://example.com/file")


def test_extractors():
    emails = extract_emails(HOME_HTML)
    assert "sales@riyadhflowers.example" in emails
    phones = extract_phones(HOME_HTML)
    assert "+966509998877" in phones
    social = extract_social_profiles(HOME_HTML)
    networks = {s["network"] for s in social}
    assert "facebook" in networks
    structured = extract_json_ld_business(HOME_HTML)
    assert "Riyadh Flowers" in structured["names"]
    assert "hello@riyadhflowers.example" in structured["emails"]


def test_crawler_with_mock_http(monkeypatch):
    # Bypass DNS SSRF resolution for example.com-style hosts used in tests
    from app.enrichment.ssrf import SafeURL, SSRFError as SSRFErr
    from urllib.parse import urlparse
    import app.enrichment.crawler as crawler_mod

    def fake_validate(url: str):
        parsed = urlparse(url)
        if parsed.hostname in {"localhost", "127.0.0.1"}:
            raise SSRFErr("blocked")
        return SafeURL(url=url, hostname=parsed.hostname or "", resolved_ips=["93.184.216.34"])

    monkeypatch.setattr(crawler_mod, "validate_public_http_url", fake_validate)
    monkeypatch.setattr(
        crawler_mod,
        "validate_redirect_target",
        lambda url, original_host: fake_validate(url),
    )

    transport = httpx.MockTransport(_mock_transport)
    client = httpx.Client(transport=transport, follow_redirects=False)
    crawler = WebsiteCrawler(client=client, rate_limit_seconds=0)
    result = crawler.crawl("https://riyadhflowers.example")
    assert len(result.pages) >= 1
    assert "sales@riyadhflowers.example" in result.emails or "hello@riyadhflowers.example" in result.emails
    assert result.phones
    assert result.social_profiles


@pytest.mark.asyncio
async def test_enrichment_execution_persists_contacts(
    db_session: AsyncSession,
    admin_user,
    monkeypatch,
):
    provider = (
        await db_session.execute(
            select(DataProvider).where(DataProvider.provider_type == "public_website")
        )
    ).scalar_one_or_none()
    if provider is None:
        provider = DataProvider(
            id=uuid.uuid4(),
            name="Public Website Enrichment",
            provider_type="public_website",
            is_active=True,
            policy_reference="public-website-robots-v1",
            data_retention_policy={"persist_crm_fields": True},
        )
        db_session.add(provider)

    business = Business(
        id=uuid.uuid4(),
        business_name="Riyadh Flowers",
        website_url="https://riyadhflowers.example",
        lead_status="new",
        business_status="unknown",
    )
    db_session.add(business)
    await db_session.flush()

    from app.models.discovery_job import EnrichmentJob
    from datetime import datetime, timezone

    job = EnrichmentJob(
        id=uuid.uuid4(),
        business_id=business.id,
        job_type="website_discovery",
        status="queued",
        scheduled_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.commit()

    from app.enrichment.ssrf import SafeURL
    from urllib.parse import urlparse
    import app.enrichment.crawler as crawler_mod

    def fake_validate(url: str):
        parsed = urlparse(url)
        return SafeURL(url=url, hostname=parsed.hostname or "", resolved_ips=["93.184.216.34"])

    monkeypatch.setattr(crawler_mod, "validate_public_http_url", fake_validate)
    monkeypatch.setattr(
        crawler_mod,
        "validate_redirect_target",
        lambda url, original_host: fake_validate(url),
    )

    transport = httpx.MockTransport(_mock_transport)
    client = httpx.Client(transport=transport, follow_redirects=False)
    crawler = WebsiteCrawler(client=client, rate_limit_seconds=0)

    with patch("app.workers.validation_tasks.run_validation_job.delay") as mock_delay:
        sync = SyncSessionLocal()
        try:
            result = EnrichmentExecutionService(sync, crawler=crawler).execute_job(job.id)
            sync.commit()
        finally:
            sync.close()
        assert mock_delay.called

    assert result["status"] == "completed"
    contacts = (
        await db_session.execute(
            select(BusinessContact).where(BusinessContact.business_id == business.id)
        )
    ).scalars().all()
    types = {c.contact_type for c in contacts}
    assert "business_email" in types
    assert "business_phone" in types
    assert "social_profile" in types


@pytest.mark.asyncio
async def test_enrichment_api_requires_website(client: AsyncClient):
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": client.admin_email, "password": client.admin_password},
    )
    token = login.json()["data"]["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = await client.post(
        "/api/v1/businesses",
        headers=headers,
        json={"business_name": "No Website Shop", "skip_dedupe": True},
    )
    business_id = created.json()["data"]["business"]["id"]

    response = await client.post(
        f"/api/v1/enrichment/businesses/{business_id}/run",
        headers=headers,
    )
    assert response.status_code == 400
