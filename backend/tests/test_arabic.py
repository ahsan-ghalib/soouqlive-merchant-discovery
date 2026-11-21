"""Arabic normalization unit tests."""

from app.utils.arabic import normalize_arabic, normalize_business_name


def test_alef_variants():
    assert normalize_arabic("أحمد") == normalize_arabic("احمد")
    assert normalize_arabic("إبراهيم") == normalize_arabic("ابراهيم")


def test_ya_and_teh_marbuta():
    assert normalize_arabic("مطعمى") == normalize_arabic("مطعمي")
    assert normalize_arabic("حديقة") == normalize_arabic("حديقه")


def test_diacritics_and_tatweel():
    assert normalize_arabic("مَطْعَم") == normalize_arabic("مطعم")
    assert normalize_arabic("مـطـعـم") == normalize_arabic("مطعم")


def test_normalize_business_name_preserves_matchability():
    assert normalize_business_name("Café Riyadh") != ""
    assert normalize_business_name("مطعم الرياض") == normalize_business_name("مَطعم الـرياض")
