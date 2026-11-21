# GEOLOGIA Research Sync — review-first automation

## What runs

The GitHub Actions workflow `.github/workflows/research-sync.yml` runs weekly (Monday 06:25 UTC) and can also be started manually. It queries the Crossref public REST API for recent records using curated geology, Earth-observation, geohazard, mineral exploration, hydrogeology, and planetary geology search terms.

The script writes `docs/research/research_candidates.json`, a review inbox containing DOI, title, authors, publication/date, provider URL, abstract excerpt when available, matched topic/technology terms, a transparent keyword relevance score, and a review checklist. DOI-derived IDs deduplicate records across queries and syncs. Existing review status and notes are preserved where possible.

## Review and promotion workflow

1. The automation opens or updates a draft-like review PR titled `chore(research): refresh geoscience review inbox`.
2. Review candidates in the JSON and linked publication pages.
3. Add PR comments to discuss evidence, usefulness, quality, and possible application.
4. Only after approval, create a separate change that adds a stable bibliographic reference, dataset adapter, algorithm, or test to GEOLOGIA.
5. The maintainer reviews and merges that separate implementation PR.

**This automation does not automatically convert paper claims into executable code.** Research abstracts and provider metadata are not enough to safely generate scientific algorithms. A proposed implementation must include source citation, domain assumptions, units, validation data, uncertainty handling, tests, and an independent review. This prevents an unverified paper or malicious linked content from silently changing the application.

## Data and safety boundaries

- Metadata and a bounded abstract excerpt only; no full-text bulk downloads.
- No research source code is executed.
- No automatic approval of scientific conclusions.
- No automatic changes to runtime application logic.
- Crossref is a discovery index, not a quality certification.
- Review source identity, publication status, corrections/retractions, licensing, reproducibility, and regional applicability.
- Candidate inbox is limited to the latest configured publication window and up to 500 records.

## CI token setup

The workflow has least-privilege `contents: write` and `pull-requests: write` permissions. GitHub's default `GITHUB_TOKEN` may not trigger other workflows for PRs it creates. For automatic CI on the generated PR, create a fine-grained repository token with only Contents and Pull requests write access and add it as the repository Actions secret `RESEARCH_SYNC_TOKEN`. The workflow uses that secret when present and falls back to `GITHUB_TOKEN` otherwise. Never commit the token.

## Provider expansion

Crossref is the initial metadata provider. Future providers (e.g. OpenAlex, institutional repositories, USGS/GSJ/BGS/CGS portals, satellite mission data portals, and DOI-backed datasets) should be added through explicit adapters with API/robots, license, rate-limit, and provenance checks. Do not crawl the existing institutional seed catalog indiscriminately.

## From candidate to application reference

The app reference registry is `src/geologia/data/approved_research_references.json`. Candidates remain unapproved in the inbox until a reviewer changes the candidate's `review_status` to `approved_for_reference` in the research-sync PR and merges that PR. The merge-triggered promotion workflow then opens a second draft PR containing only validated bibliographic fields (DOI, title, authors, date, publisher, URL, and topic tags). Review and merge that second PR to add the reference to the app registry.

A PR comment is useful for discussion and evidence notes; comments alone do not silently approve or promote a paper. The explicit status edit and merged review PR are the approval gate. Promotion is idempotent and does not copy abstracts or convert paper findings into code.
