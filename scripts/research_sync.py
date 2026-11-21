#!/usr/bin/env python3
"""Fetch recent geoscience research metadata into a human-review inbox.

This script does not download papers, run their code, claim scientific validity,
or write executable application code. It records source metadata and evidence
snippets so a maintainer can review and selectively promote references.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "research" / "research_candidates.json"
WINDOW_DAYS = int(os.environ.get("RESEARCH_WINDOW_DAYS", "180"))
MAX_PER_QUERY = int(os.environ.get("RESEARCH_MAX_PER_QUERY", "30"))
MAX_ITEMS = 500
API = "https://api.crossref.org/works"

QUERIES = (
    "geological mapping machine learning",
    "geoscience remote sensing satellite",
    "geological hazards monitoring technology",
    "mineral exploration geophysics artificial intelligence",
    "hydrogeology groundwater modeling",
    "planetary geology remote sensing",
    "geospatial earth observation geology",
)

TOPIC_TERMS = {
    "geology", "geological", "geoscience", "geoscientific", "stratigraphy",
    "tectonic", "mineral", "ore", "geochemistry", "geophysics", "petrology",
    "hydrogeology", "groundwater", "geomorphology", "volcan", "earthquake",
    "landslide", "seismic", "remote sensing", "satellite", "earth observation",
    "geospatial", "gis", "digital elevation", "borehole", "reservoir",
    "subsurface", "planetary", "lithology", "sediment", "mapping",
}
TECH_TERMS = {
    "machine learning", "deep learning", "artificial intelligence", "neural",
    "computer vision", "automation", "digital twin", "inversion", "sensor",
    "hyperspectral", "sar", "lidar", "insar", "foundation model",
    "data assimilation", "simulation", "numerical modeling", "workflow",
}


def clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\\s+", " ", value).strip()


def date_from_crossref(item: dict) -> str | None:
    for key in ("published-online", "published-print", "published", "created"):
        parts = item.get(key, {}).get("date-parts", [])
        if parts and parts[0]:
            p = parts[0]
            try:
                return datetime(int(p[0]), int(p[1]) if len(p) > 1 else 1,
                               int(p[2]) if len(p) > 2 else 1,
                               tzinfo=timezone.utc).date().isoformat()
            except (ValueError, TypeError):
                continue
    return None


def make_candidate(item: dict, query: str, cutoff: datetime) -> dict | None:
    title = clean_text((item.get("title") or [""])[0])
    abstract = clean_text(item.get("abstract", ""))
    doi = clean_text(item.get("DOI", "")).lower()
    published = date_from_crossref(item)
    if not title or not doi or not published:
        return None
    try:
        pubdate = datetime.fromisoformat(published).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    if pubdate < cutoff:
        return None

    searchable = (title + " " + abstract).lower()
    topic_hits = sorted(term for term in TOPIC_TERMS if term in searchable)
    tech_hits = sorted(term for term in TECH_TERMS if term in searchable)
    score = min(10, len(topic_hits) * 2 + len(tech_hits))
    if len(topic_hits) < 1 or score < 3:
        return None

    authors = []
    for author in item.get("author", [])[:8]:
        name = " ".join(x for x in (author.get("given"), author.get("family")) if x)
        if name:
            authors.append(name)
    container = clean_text((item.get("container-title") or [""])[0])
    stable = hashlib.sha256(doi.encode("utf-8")).hexdigest()[:16]
    abstract_excerpt = abstract[:1800] if abstract else ""
    return {
        "candidate_id": "cr-" + stable,
        "provider": "Crossref",
        "doi": doi,
        "title": title,
        "authors": authors,
        "publication": container,
        "published_date": published,
        "landing_page": item.get("URL") or "https://doi.org/" + doi,
        "abstract_excerpt": abstract_excerpt,
        "discovery_query": query,
        "matched_geoscience_terms": topic_hits,
        "matched_technology_terms": tech_hits,
        "relevance_score": score,
        "review_status": "needs_human_review",
        "review_checklist": [
            "Verify publication and source identity",
            "Check methods, data, uncertainty, and validation",
            "Check license and reuse rights",
            "Decide whether to add a stable reference to GEOLOGIA",
            "Only after review, propose any code or knowledge-base change",
        ],
    }


def fetch_query(query: str, cutoff: datetime) -> list[dict]:
    params = {
        "query.bibliographic": query,
        "filter": "from-pub-date:" + cutoff.date().isoformat(),
        "rows": str(MAX_PER_QUERY),
        "sort": "published",
        "order": "desc",
        "select": "DOI,title,author,container-title,published,published-online,published-print,created,abstract,URL",
    }
    url = API + "?" + urlencode(params)
    request = Request(url, headers={
        "User-Agent": "GEOLOGIA-ResearchSync/0.1 (metadata-only; contact: maintainer via repository)",
        "Accept": "application/json",
    })
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    records = payload.get("message", {}).get("items", [])
    result = []
    for item in records:
        candidate = make_candidate(item, query, cutoff)
        if candidate:
            result.append(candidate)
    return result


def build_inbox(previous: dict | None = None) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=WINDOW_DAYS)
    existing = {
        item.get("candidate_id"): item
        for item in (previous or {}).get("candidates", [])
        if item.get("candidate_id")
    }
    errors = []
    fresh = []
    for query in QUERIES:
        try:
            fresh.extend(fetch_query(query, cutoff))
        except Exception as exc:  # retain partial results; surface provider failures
            errors.append({"provider": "Crossref", "query": query, "error": str(exc)[:300]})
        time.sleep(1.0)

    for item in fresh:
        old = existing.get(item["candidate_id"], {})
        item["first_seen"] = old.get("first_seen", now.isoformat())
        item["last_seen"] = now.isoformat()
        # Preserve human review state and notes on subsequent syncs.
        item["review_status"] = old.get("review_status", "needs_human_review")
        if old.get("review_notes"):
            item["review_notes"] = old["review_notes"]
        existing[item["candidate_id"]] = item

    candidates = sorted(
        (x for x in existing.values() if x.get("published_date", "") >= cutoff.date().isoformat()),
        key=lambda x: (x.get("published_date", ""), x.get("relevance_score", 0)),
        reverse=True,
    )[:MAX_ITEMS]
    return {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "sync_window_days": WINDOW_DAYS,
        "provider": "Crossref REST API",
        "provider_url": "https://api.crossref.org/",
        "mode": "metadata_and_abstract_excerpt_only",
        "status": "review_inbox_not_approved_references",
        "candidate_count": len(candidates),
        "provider_errors": errors,
        "policy": {
            "no_fulltext_download": True,
            "no_source_code_execution": True,
            "no_automatic_scientific_claim_approval": True,
            "no_automatic_application_code_changes": True,
            "human_review_and_pull_request_required": True,
        },
        "candidates": candidates,
    }


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    if OUTPUT.exists():
        try:
            previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"Invalid existing inbox JSON: {OUTPUT}", file=sys.stderr)
            return 2
    inbox = build_inbox(previous)
    OUTPUT.write_text(json.dumps(inbox, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {inbox['candidate_count']} review candidates to {OUTPUT}")
    if inbox["provider_errors"]:
        print(f"Provider query errors: {len(inbox['provider_errors'])}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
