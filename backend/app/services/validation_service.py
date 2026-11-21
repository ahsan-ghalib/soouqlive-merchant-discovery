"""Post-enrichment validation (syntax/DNS/MX/duplicates)."""

from __future__ import annotations

import logging
import socket
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.contact import BusinessContact
from app.utils.email import is_valid_email_syntax, normalize_email
from app.utils.normalization import normalize_domain
from app.utils.phone import normalize_phone

logger = logging.getLogger(__name__)


class ValidationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def validate_business(self, business: Business) -> dict[str, Any]:
        contacts = (
            self.session.execute(
                select(BusinessContact).where(BusinessContact.business_id == business.id)
            )
            .scalars()
            .all()
        )

        email_results = []
        phone_results = []
        flags: list[str] = []

        for contact in contacts:
            if contact.contact_type == "business_email":
                email_results.append(self._validate_email_contact(contact))
            elif contact.contact_type == "business_phone":
                phone_results.append(self._validate_phone_contact(contact))

        website_ok = True
        domain = normalize_domain(business.website_url)
        if business.website_url and not domain:
            website_ok = False
            flags.append("invalid_website")
        elif domain:
            # Duplicate domain detection
            others = (
                self.session.execute(
                    select(Business).where(
                        Business.id != business.id,
                        Business.website_url.is_not(None),
                    ).limit(500)
                )
                .scalars()
                .all()
            )
            for other in others:
                if normalize_domain(other.website_url) == domain:
                    flags.append(f"duplicate_domain:{other.id}")
                    break

        # Conflicting phones: multiple different primary normalized phones
        phones = [
            c.normalized_value
            for c in contacts
            if c.contact_type == "business_phone" and c.normalized_value
        ]
        if len(set(phones)) > 3:
            flags.append("many_distinct_phones")

        # Mark syntax-valid emails with verification_method dns_mx when MX ok
        for item in email_results:
            if item.get("mx_ok") and item.get("contact_id"):
                contact = self.session.get(BusinessContact, UUID(item["contact_id"]))
                if contact and not contact.is_verified:
                    contact.verification_method = "dns_mx_check"
                    # DNS/MX does NOT prove mailbox existence or marketing consent
        self.session.flush()

        return {
            "website_ok": website_ok,
            "website_domain": domain,
            "emails": email_results,
            "phones": phone_results,
            "flags": flags,
            "note": (
                "DNS/MX verification does not prove an email exists "
                "or that its owner consented to marketing."
            ),
        }

    def _validate_email_contact(self, contact: BusinessContact) -> dict[str, Any]:
        normalized = normalize_email(contact.contact_value)
        syntax_ok = bool(normalized) and is_valid_email_syntax(normalized or "")
        mx_ok = False
        domain = None
        if syntax_ok and normalized:
            domain = normalized.split("@", 1)[1]
            mx_ok = self._has_mx_or_a(domain)
            contact.normalized_value = normalized
        return {
            "contact_id": str(contact.id),
            "value": contact.contact_value,
            "normalized": normalized,
            "syntax_ok": syntax_ok,
            "domain": domain,
            "mx_ok": mx_ok,
        }

    def _validate_phone_contact(self, contact: BusinessContact) -> dict[str, Any]:
        normalized = normalize_phone(contact.contact_value)
        ok = normalized is not None
        if ok:
            contact.normalized_value = normalized
            # Duplicate phone across businesses
            dup = (
                self.session.execute(
                    select(func.count())
                    .select_from(BusinessContact)
                    .where(
                        BusinessContact.contact_type == "business_phone",
                        BusinessContact.normalized_value == normalized,
                        BusinessContact.business_id != contact.business_id,
                    )
                ).scalar_one()
            )
        else:
            dup = 0
        return {
            "contact_id": str(contact.id),
            "value": contact.contact_value,
            "normalized": normalized,
            "e164_ok": ok,
            "duplicate_count": int(dup or 0),
        }

    def _has_mx_or_a(self, domain: str) -> bool:
        try:
            import dns.resolver  # type: ignore

            try:
                answers = dns.resolver.resolve(domain, "MX")
                if answers:
                    return True
            except Exception:
                pass
            try:
                answers = dns.resolver.resolve(domain, "A")
                return bool(answers)
            except Exception:
                return False
        except ImportError:
            # Fallback without dnspython: socket getaddrinfo
            try:
                socket.getaddrinfo(domain, 25)
                return True
            except socket.gaierror:
                return False
