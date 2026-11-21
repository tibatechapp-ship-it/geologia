import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import promote_approved_references as promoter


def candidate(status="approved_for_reference"):
    return {
        "candidate_id": "cr-approved-001",
        "provider": "Crossref",
        "doi": "10.1234/example",
        "title": "Geological mapping with remote sensing",
        "authors": ["Example Author"],
        "publication": "Example Geoscience Journal",
        "published_date": "2025-05-01",
        "landing_page": "https://doi.org/10.1234/example",
        "matched_geoscience_terms": ["geological", "mapping"],
        "matched_technology_terms": ["remote sensing"],
        "review_status": status,
    }


def test_only_explicitly_approved_candidates_are_promoted():
    inbox = {"candidates": [candidate("needs_human_review")]}
    registry = {"schema_version": 1, "references": []}
    updated, count = promoter.promote(inbox, registry)
    assert count == 0
    assert updated["references"] == []


def test_approved_candidate_is_promoted_idempotently():
    inbox = {"candidates": [candidate()]}
    registry = {"schema_version": 1, "references": []}
    updated, count = promoter.promote(inbox, registry)
    assert count == 1
    assert updated["references"][0]["doi"] == "10.1234/example"
    assert updated["references"][0]["review_status"] == "human_approved_bibliographic_reference"
    again, second_count = promoter.promote(inbox, updated)
    assert second_count == 0
    assert len(again["references"]) == 1


def test_invalid_or_non_https_reference_is_rejected():
    item = candidate()
    item["landing_page"] = "http://example.org/paper"
    assert promoter.valid_candidate(item) is False
