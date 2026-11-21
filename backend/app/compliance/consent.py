"""Consent purpose/channel constants and helpers."""

from __future__ import annotations

CONSENT_PURPOSES = {
    "promotional_email",
    "promotional_sms",
    "promotional_whatsapp",
    "business_follow_up",
    "advertising_audience_upload",
}

CONSENT_CHANNELS = {
    "email",
    "sms",
    "whatsapp",
    "phone",
    "ads_platform",
}

CONSENT_STATUSES = {"granted", "denied", "withdrawn", "pending"}

CONSENT_METHODS = {
    "written_form",
    "digital_opt_in",
    "recorded_call",
    "merchant_portal",
    "manual_evidence",
}

# Mapping purpose → required channel family
PURPOSE_CHANNEL_MAP = {
    "promotional_email": {"email"},
    "promotional_sms": {"sms"},
    "promotional_whatsapp": {"whatsapp"},
    "business_follow_up": {"email", "sms", "whatsapp", "phone"},
    "advertising_audience_upload": {"ads_platform", "email"},
}


def purpose_matches_channel(purpose: str, channel: str) -> bool:
    allowed = PURPOSE_CHANNEL_MAP.get(purpose)
    if not allowed:
        return False
    return channel in allowed
