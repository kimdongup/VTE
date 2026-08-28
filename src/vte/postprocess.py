from __future__ import annotations

import re

_CLEAN_RE = re.compile(r"[ \t\u3000]+")
_SYMBOLS_RE = re.compile(r"(.)\1{3,}")


def normalize(text: str) -> str:
    """Clean common OCR noise from a recognized string."""
    text = text.replace("\n", " ")
    text = _CLEAN_RE.sub(" ", text).strip()
    text = _SYMBOLS_RE.sub(r"\1", text)
    return text.strip()


def is_mostly_korean(text: str, ratio: float = 0.3) -> bool:
    """True when the share of Hangul syllables meets ``ratio``.

    Strings with no letters at all (pure digits/punct) pass through so that
    numeric subtitles are not silently dropped.
    """
    if not text:
        return False
    hangul = sum(1 for ch in text if "\uac00" <= ch <= "\ud7a3")
    letters = sum(1 for ch in text if ch.isalpha())
    if letters == 0:
        return True
    return hangul / len(text) >= ratio or hangul / letters >= ratio
