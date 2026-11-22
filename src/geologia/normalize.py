"""Arabic/Latin normalization adapted from Ali-Algomori.

Source: tibatechapp-ship-it/Ali-Algomori
Original file: src/geologia/normalize.py
Reuse authorized by the project owner on 2026-11-22 (GEOLOGIA issue #98).

This module only canonicalizes text for deterministic matching. It does not
translate content, alter scientific data, or provide scientific validation.
"""
from __future__ import annotations

import re

# Arabic diacritics, Quranic annotation marks, small high marks and tatweel.
_AR_DIACRITICS = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]"
)

# Fold orthographic variants to canonical base letters for keyword matching.
_AR_VARIANTS = str.maketrans({
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ٱ": "ا",
    "ؤ": "و",
    "ئ": "ي",
    "ى": "ي",
    "ة": "ه",
})

_NON_WORD = re.compile(r"[^\w\s]+", re.UNICODE)


def normalize_arabic(text: str) -> str:
    """Remove Arabic marks and fold common orthographic variants."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return _AR_DIACRITICS.sub("", text).translate(_AR_VARIANTS)


def normalize_text(text: str) -> str:
    """Return a lowercase, punctuation-normalized Arabic/Latin match key."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    text = normalize_arabic(text.lower())
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.split())


def is_normalized_idempotent(text: str) -> bool:
    """Check whether normalizing an already normalized string is stable."""
    once = normalize_text(text)
    return once == normalize_text(once)
