import json
from pathlib import Path
from urllib.parse import urlparse

CATALOG_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "geologia"
    / "data"
    / "ali_geoscience_source_catalog.json"
)


def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_ali_source_catalog_has_unique_stable_ids_and_valid_https_urls():
    catalog = load_catalog()
    institutions = catalog["institutions"]
    ids = [item["id"] for item in institutions]

    assert len(ids) == len(set(ids))
    assert len(institutions) >= 19

    for item in institutions:
        assert item["id"]
        assert item["name"]
        parsed = urlparse(item["discovery_url"])
        assert parsed.scheme == "https"
        assert parsed.netloc
        assert item["language_codes"]
        assert item["topics"]
        assert item["source_priority"] == "primary"


def test_catalog_covers_original_and_new_requested_countries():
    catalog = load_catalog()
    countries = {item["country"] for item in catalog["institutions"]}
    languages = {
        language
        for item in catalog["institutions"]
        for language in item["language_codes"]
    }

    expected_countries = {
        "United States", "United Kingdom", "Russia", "China", "Yemen",
        "Türkiye", "Malaysia", "Indonesia", "Venezuela", "Pakistan",
        "Afghanistan", "Algeria", "Morocco", "Mauritania", "Sudan",
    }
    assert expected_countries <= countries
    assert {"en", "ru", "zh", "ar", "tr", "ms", "id", "es", "ur", "fa", "ps", "fr"} <= languages


def test_catalog_does_not_claim_seeds_are_ingested_or_license_cleared():
    catalog = load_catalog()

    assert catalog["catalog_status"] == "discovery_seeds_not_ingested"
    assert catalog["policy"]["default_access"] == "metadata_only_until_access_and_license_review"
    assert catalog["policy"]["never_execute_source_content"] is True
    assert catalog["policy"]["never_treat_source_homepage_as_verified_dataset"] is True

    unverified = [
        item for item in catalog["institutions"]
        if item["discovery_status"] == "seed_homepage_unverified"
    ]
    assert unverified
    assert all(item.get("review_note") for item in unverified)
