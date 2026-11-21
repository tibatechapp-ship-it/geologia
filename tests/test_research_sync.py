from datetime import datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import research_sync


def test_clean_text_strips_markup_and_normalizes_whitespace():
    assert research_sync.clean_text("<p>Geo\n  science</p>") == "Geo science"


def test_candidate_requires_doi_title_date_and_geoscience_relevance():
    cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candidate = research_sync.make_candidate(
        {
            "DOI": "10.1234/example",
            "title": ["Machine learning for geological mapping"],
            "published": {"date-parts": [[2025, 5, 1]]},
            "author": [{"given": "Ada", "family": "Researcher"}],
            "container-title": ["Journal of Geoscience"],
            "abstract": "We use machine learning and remote sensing for geological mapping.",
            "URL": "https://doi.org/10.1234/example",
        },
        "geological mapping machine learning",
        cutoff,
    )
    assert candidate is not None
    assert candidate["candidate_id"].startswith("cr-")
    assert candidate["doi"] == "10.1234/example"
    assert candidate["review_status"] == "needs_human_review"
    assert candidate["review_checklist"]


def test_candidate_rejects_unrelated_or_old_records():
    cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
    unrelated = {
        "DOI": "10.1234/unrelated",
        "title": ["A study of social behavior"],
        "published": {"date-parts": [[2025, 5, 1]]},
    }
    old = {
        "DOI": "10.1234/old",
        "title": ["Geological mapping with machine learning"],
        "published": {"date-parts": [[2020, 1, 1]]},
        "abstract": "geological mapping machine learning",
    }
    assert research_sync.make_candidate(unrelated, "general", cutoff) is None
    assert research_sync.make_candidate(old, "geology", cutoff) is None
