#!/usr/bin/env python3
"""Promote explicitly approved bibliographic candidates into the app registry."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INBOX = ROOT / "docs" / "research" / "research_candidates.json"
REGISTRY = ROOT / "src" / "geologia" / "data" / "approved_research_references.json"
APPROVED_STATUS = "approved_for_reference"


def valid_candidate(item: dict) -> bool:
    doi = item.get("doi")
    title = item.get("title")
    url = item.get("landing_page")
    date = item.get("published_date")
    if not all(isinstance(value, str) and value.strip() for value in (doi, title, url, date)):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.netloc) and doi.lower().startswith("10.")


def promote(inbox: dict, registry: dict) -> tuple[dict, int]:
    known = {item.get("reference_id") for item in registry.get("references", [])}
    added = []
    promoted_at = datetime.now(timezone.utc).isoformat()
    for candidate in inbox.get("candidates", []):
        if candidate.get("review_status") != APPROVED_STATUS:
            continue
        candidate_id = candidate.get("candidate_id")
        if not candidate_id or candidate_id in known or not valid_candidate(candidate):
            continue
        added.append({
            "reference_id": candidate_id,
            "provider": candidate.get("provider", "Crossref"),
            "doi": candidate["doi"],
            "title": candidate["title"],
            "authors": candidate.get("authors", []),
            "publication": candidate.get("publication", ""),
            "published_date": candidate["published_date"],
            "landing_page": candidate["landing_page"],
            "topics": sorted(set(candidate.get("matched_geoscience_terms", []))),
            "technology_tags": sorted(set(candidate.get("matched_technology_terms", []))),
            "review_status": "human_approved_bibliographic_reference",
            "promoted_at": promoted_at,
        })
        known.add(candidate_id)
    updated = dict(registry)
    updated["references"] = sorted(
        registry.get("references", []) + added,
        key=lambda item: (item.get("published_date", ""), item.get("title", "")),
        reverse=True,
    )
    return updated, len(added)


def main() -> int:
    if not INBOX.exists() or not REGISTRY.exists():
        raise SystemExit("Research inbox or approved reference registry is missing")
    inbox = json.loads(INBOX.read_text(encoding="utf-8"))
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    updated, count = promote(inbox, registry)
    if count:
        REGISTRY.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Promoted {count} explicitly approved bibliographic references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
