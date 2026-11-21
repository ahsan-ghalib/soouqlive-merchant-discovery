"""Outbound HTML email templates."""

from __future__ import annotations

from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent
ASSETS_DIR = TEMPLATES_DIR / "assets"

VENDOR_OUTREACH = "vendor_outreach"
VENDOR_OUTREACH_SUBJECT = "سجّل متجرك مجانًا على سوق لايف — بدون عمولة"

VENDOR_OUTREACH_TEXT = (
    "سجّل متجرك مجانًا على سوق لايف، دون رسوم تسجيل أو عمولة على المبيعات.\n"
    "Register your store free on SOOUQ LIVE. No registration fees. Zero sales commission.\n"
    "https://soouqlive.com/register/vendor?utm_source=email&utm_medium=email&utm_campaign=vendor_outreach"
)


def load_template(name: str) -> str:
    path = TEMPLATES_DIR / f"{name}.html"
    if not path.is_file():
        raise FileNotFoundError(f"Email template not found: {name}")
    return path.read_text(encoding="utf-8")


def logo_path() -> Path:
    return ASSETS_DIR / "logo.png"
