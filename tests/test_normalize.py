import pytest

from geologia.normalize import (
    is_normalized_idempotent,
    normalize_arabic,
    normalize_text,
)


def test_arabic_diacritics_and_tatweel_are_removed():
    assert normalize_text("المِيَاهُ الجَوْفِيَّة") == "المياه الجوفيه"


def test_arabic_hamza_and_letter_variants_are_folded():
    assert normalize_text("إِرْتِفَاع آبار") == "ارتفاع ابار"
    assert normalize_text("مسؤولية") == "مسووليه"
    assert normalize_text("فتى") == "فتي"


def test_latin_case_punctuation_and_whitespace_are_normalized():
    assert normalize_text("  GROUNDWATER:  Water-Table! ") == "groundwater water table"


def test_normalization_is_idempotent_for_mixed_arabic_and_latin():
    value = "المِيَاهُ الجَوْفِيَّة / Groundwater"
    assert is_normalized_idempotent(value)
    assert normalize_text(normalize_text(value)) == normalize_text(value)


@pytest.mark.parametrize("value", [None, 3, [], {}])
def test_normalizer_rejects_non_strings(value):
    with pytest.raises(TypeError, match="text must be a string"):
        normalize_arabic(value)


def test_text_normalizer_rejects_non_strings(value):
    with pytest.raises(TypeError, match="text must be a string"):
        normalize_text(value)
