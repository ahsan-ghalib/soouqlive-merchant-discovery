"""SSRF-safe public website crawler with robots.txt respect."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.enrichment.email_extractor import extract_emails
from app.enrichment.parser import discover_relevant_links
from app.enrichment.phone_extractor import extract_phones
from app.enrichment.social_extractor import extract_social_profiles
from app.enrichment.ssrf import SSRFError, validate_public_http_url, validate_redirect_target
from app.enrichment.structured_data import extract_json_ld_business

logger = logging.getLogger(__name__)

USER_AGENT = "SoouqLiveMerchantBot/0.1 (+internal-research; respectful-crawler)"


@dataclass
class PageResult:
    url: str
    status_code: int
    html: str
    final_url: str


@dataclass
class CrawlResult:
    start_url: str
    pages: list[PageResult] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    social_profiles: list[dict[str, str]] = field(default_factory=list)
    structured: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    robots_allowed: bool = True


class WebsiteCrawler:
    def __init__(
        self,
        *,
        max_pages: int = 5,
        timeout_seconds: float = 10.0,
        max_response_bytes: int = 1_500_000,
        max_redirects: int = 5,
        rate_limit_seconds: float = 0.5,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self.max_pages = max_pages
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_redirects = max_redirects
        self.rate_limit_seconds = rate_limit_seconds
        self._client = client
        self._owns_client = client is None

    def crawl(self, website_url: str) -> CrawlResult:
        result = CrawlResult(start_url=website_url)
        try:
            safe = validate_public_http_url(website_url)
        except SSRFError as exc:
            result.errors.append(str(exc))
            result.robots_allowed = False
            return result

        client = self._client or httpx.Client(
            timeout=self.timeout_seconds,
            follow_redirects=False,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        try:
            if not self._robots_allowed(client, safe.url):
                result.robots_allowed = False
                result.errors.append("robots.txt disallows crawling this URL")
                return result

            homepage = self._fetch(client, safe.url, original_host=safe.hostname)
            if homepage is None:
                result.errors.append("Failed to fetch homepage")
                return result
            result.pages.append(homepage)
            self._extract_into(result, homepage)

            links = discover_relevant_links(homepage.html, homepage.final_url, limit=self.max_pages - 1)
            for link in links:
                if len(result.pages) >= self.max_pages:
                    break
                time.sleep(self.rate_limit_seconds)
                try:
                    validate_public_http_url(link)
                except SSRFError as exc:
                    result.errors.append(f"Skipped unsafe link {link}: {exc}")
                    continue
                if not self._robots_allowed(client, link):
                    result.errors.append(f"robots.txt disallows {link}")
                    continue
                page = self._fetch(client, link, original_host=safe.hostname)
                if page is None:
                    continue
                result.pages.append(page)
                self._extract_into(result, page)
        finally:
            if self._owns_client:
                client.close()

        # Deduplicate
        result.emails = sorted(set(result.emails))
        result.phones = sorted(set(result.phones))
        # social unique by network
        social_map = {s["network"]: s for s in result.social_profiles}
        result.social_profiles = list(social_map.values())
        return result

    def _extract_into(self, result: CrawlResult, page: PageResult) -> None:
        result.emails.extend(extract_emails(page.html, page.final_url))
        result.phones.extend(extract_phones(page.html))
        result.social_profiles.extend(extract_social_profiles(page.html, page.final_url))
        structured = extract_json_ld_business(page.html)
        # Merge structured
        for key, values in structured.items():
            existing = result.structured.setdefault(key, [])
            if isinstance(values, list):
                existing.extend(values)
        if structured.get("emails"):
            result.emails.extend(structured["emails"])
        if structured.get("phones"):
            # keep raw; normalization happens in service/validation
            for phone in structured["phones"]:
                result.phones.extend(extract_phones(f'<a href="tel:{phone}">{phone}</a>'))
        if structured.get("same_as"):
            fake_html = "".join(f'<a href="{u}">{u}</a>' for u in structured["same_as"])
            result.social_profiles.extend(extract_social_profiles(fake_html))

    def _robots_allowed(self, client: httpx.Client, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        try:
            # Validate robots URL too
            validate_public_http_url(robots_url)
            response = client.get(robots_url)
            if response.status_code == 404:
                return True
            if response.status_code >= 400:
                # Fail open for transient robots failures? Spec says check robots —
                # if unreachable, be conservative and allow public homepage only when 404.
                return response.status_code < 500
            if len(response.content) > self.max_response_bytes:
                return False
            rp.parse(response.text.splitlines())
        except Exception as exc:
            logger.info("robots.txt fetch failed for %s: %s", robots_url, exc)
            # Conservative: allow if robots cannot be fetched (common), but log
            return True
        return rp.can_fetch(USER_AGENT, url)

    def _fetch(
        self,
        client: httpx.Client,
        url: str,
        *,
        original_host: str,
    ) -> Optional[PageResult]:
        current = url
        for _ in range(self.max_redirects + 1):
            try:
                safe = validate_redirect_target(current, original_host)
            except SSRFError as exc:
                logger.warning("Blocked unsafe URL during fetch: %s (%s)", current, exc)
                return None

            response = client.get(safe.url)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    return None
                current = urljoin(safe.url, location)
                continue

            if response.status_code >= 400:
                logger.info("Fetch failed %s -> %s", safe.url, response.status_code)
                return None

            content_type = (response.headers.get("content-type") or "").lower()
            if "html" not in content_type and "text/" not in content_type:
                return None
            if len(response.content) > self.max_response_bytes:
                logger.info("Response too large for %s", safe.url)
                return None

            # Re-check resolved host after redirects by validating final URL
            try:
                final_safe = validate_public_http_url(str(response.url))
            except SSRFError:
                return None

            return PageResult(
                url=url,
                status_code=response.status_code,
                html=response.text,
                final_url=final_safe.url,
            )

        logger.info("Too many redirects for %s", url)
        return None
