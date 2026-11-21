"""Phone and email normalization tests."""

from app.utils.email import is_valid_email_syntax, normalize_email
from app.utils.phone import normalize_phone


def test_normalize_saudi_phone():
    assert normalize_phone("0501234567") == "+966501234567"
    assert normalize_phone("+966 50 123 4567") == "+966501234567"


def test_email_helpers():
    assert normalize_email("  Info@Example.COM ") == "info@example.com"
    assert is_valid_email_syntax("bad@") is False
