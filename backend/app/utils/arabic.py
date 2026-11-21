"""Arabic text normalization helpers."""

import re
import unicodedata

# Alef variants → ا
_ALEF_RE = re.compile(r"[إأآٱ]")
# Ya variants → ي
_YA_RE = re.compile(r"[ىي]")
# Tatweel / kashida
_TATWEEL_RE = re.compile(r"\u0640")
# Arabic diacritics (tashkeel)
_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")
# Common punctuation / whitespace collapse
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for matching while preserving original separately.

    Handles Alef/Ya variants, diacritics, tatweel, and NFKC unicode form.
    """
    if not text:
        return ""

    value = unicodedata.normalize("NFKC", text)
    value = _DIACRITICS_RE.sub("", value)
    value = _TATWEEL_RE.sub("", value)
    value = _ALEF_RE.sub("ا", value)
    value = _YA_RE.sub("ي", value)
    value = value.replace("ة", "ه")
    value = _WHITESPACE_RE.sub(" ", value).strip().lower()
    return value


def normalize_business_name(name: str) -> str:
    """Normalize a business name for deduplication lookups."""
    if not name:
        return ""
    value = normalize_arabic(name)
    # Also strip common Latin punctuation for bilingual names
    value = re.sub(r"[^\w\s\u0600-\u06FF]", " ", value, flags=re.UNICODE)
    value = _WHITESPACE_RE.sub(" ", value).strip()
    return value
