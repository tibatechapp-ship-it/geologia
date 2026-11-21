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


def test_candidate_preserves_arabic_publication_language_and_relevance():
    cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
    item = {
        "DOI": "10.1234/arabic.geo",
        "title": ["الاستشعار عن بعد للجيولوجيا باستخدام التعلم الآلي"],
        "abstract": "دراسة علوم الأرض والجيولوجيا باستخدام الاستشعار عن بعد.",
        "language": "ar",
        "published": {"date-parts": [[2025, 5, 1]]},
    }
    candidate = research_sync.make_candidate(
        item, "الاستشعار عن بعد علوم الأرض", cutoff, "ar"
    )
    assert candidate is not None
    assert candidate["publication_language"] == "ar"
    assert candidate["discovery_language"] == "ar"
    assert candidate["review_status"] == "needs_human_review"


def test_candidate_supports_russian_geoscience_metadata():
    cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
    item = {
        "DOI": "10.1234/russian.geo",
        "title": ["Геологическое картирование с машинным обучением"],
        "abstract": "Геология и дистанционное зондирование для картирования.",
        "language": "ru",
        "published": {"date-parts": [[2025, 5, 1]]},
    }
    candidate = research_sync.make_candidate(
        item, "геологическое картирование дистанционное зондирование", cutoff, "ru"
    )
    assert candidate is not None
    assert candidate["publication_language"] == "ru"
    assert candidate["discovery_language"] == "ru"


def test_candidate_supports_chinese_geoscience_metadata():
    cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
    item = {
        "DOI": "10.1234/chinese.geo",
        "title": ["地质灾害遥感监测与机器学习"],
        "abstract": "地球科学中的地质灾害和遥感数据分析。",
        "language": "zh",
        "published": {"date-parts": [[2025, 5, 1]]},
    }
    candidate = research_sync.make_candidate(
        item, "地震 地质灾害", cutoff, "zh"
    )
    assert candidate is not None
    assert candidate["publication_language"] == "zh"
    assert candidate["discovery_language"] == "zh"


def test_research_discovery_queries_cover_four_languages():
    assert set(research_sync.QUERY_GROUPS) == {"en", "ar", "ru", "zh"}
    assert all(research_sync.QUERY_GROUPS.values())
    assert any(language == "ar" for language, _ in research_sync.QUERIES)
