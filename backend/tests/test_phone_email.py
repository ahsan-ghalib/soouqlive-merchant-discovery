"""Phone and email normalization tests."""

from app.utils.email import is_junk_email, is_valid_email_syntax, normalize_email
from app.utils.phone import normalize_phone


def test_normalize_saudi_phone():
    assert normalize_phone("0501234567") == "+966501234567"
    assert normalize_phone("+966 50 123 4567") == "+966501234567"


def test_email_helpers():
    assert normalize_email("  Info@Example.COM ") is None  # example.com junk
    assert normalize_email("  Info@Business.COM ") == "info@business.com"
    assert is_valid_email_syntax("bad@") is False


def test_rejects_asset_and_entity_scrapes():
    assert is_junk_email("asset-60@2x-8-225x300.png")
    assert normalize_email("asset-60@2x-8-225x300.png") is None
    assert normalize_email("godiva_belgium@2x.png") is None
    assert normalize_email("u003eservice@hrewards.com") == "service@hrewards.com"
