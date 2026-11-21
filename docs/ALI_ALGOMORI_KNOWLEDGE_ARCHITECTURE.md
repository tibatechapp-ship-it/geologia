# Ali Algomori — Scientific Knowledge Architecture

**Status:** Local retrieval foundation implemented; source catalog remains discovery-only until human review and explicit local ingestion  
**Owner:** GEOLOGIA  
**Scope:** Scientific knowledge and retrieval for the proposed Ali Algomori geoscience agent

This document defines the knowledge system before any model training. It does not claim that Ali is currently connected to the application, that the source catalog has been crawled, or that a fine-tuned model exists.

## 1. Agent responsibility

Ali Algomori is proposed as the geoscience knowledge and evidence coordinator. He should:

- identify the geological question, region, scale, time interval, and data types;
- delegate bounded tasks to specialist roles (stratigraphy, tectonics, mineralogy, petrology, geophysics, geochemistry, hydrogeology, GIS/remote sensing);
- retrieve primary evidence and preserve source-level provenance;
- distinguish source statements, computed results, interpretations, and hypotheses;
- detect disagreement and missing evidence;
- abstain or request data when the evidence does not support a conclusion.

This is a proposed scientific role. The existing application’s deterministic chief-agent routing is not replaced by this document.

## 2. Knowledge layers

1. **Source catalog:** institutions, repositories, APIs, language, access policy, license state, and discovery status.
2. **Immutable source records:** original file or record identifier, retrieval date, checksum, version, language, license evidence, and canonical URL.
3. **Extracted evidence:** page/section/table/figure location, verbatim source span where legally permitted, normalized text, extraction tool/version, and quality flags.
4. **Knowledge claims:** small atomic claims linked to one or more evidence records. Claims may be supported, contradicted, qualified, or superseded.
5. **Geoscience graph:** spatial and temporal relationships among formations, lithologies, minerals, faults, basins, samples, boreholes, events, and publications.
6. **Agent working memory:** task-scoped context, hypotheses, tool results, and unresolved questions; expires or is archived after task completion.
7. **Model training corpus:** separately curated examples with license clearance, decontamination, splits, and evaluation. It is not a dump of the retrieval index.

## 3. Evidence record contract

Each claim must include:

- stable claim ID and normalized claim text;
- source ID, publisher, author(s), publication date and version;
- DOI or stable identifier when available;
- page, section, table, figure, sample, or dataset row locator;
- source language and original text pointer;
- region/geometry and geological time range when known;
- units, coordinate reference system, datum, and conventions where applicable;
- license/access evidence and allowed processing;
- extraction method and software version;
- review state, confidence rationale, and known limitations.

Do not promote a source homepage, abstract, AI-generated summary, or unverified metadata into a scientific fact.

## 4. Source acquisition rules

- Begin with metadata discovery and manually verified source endpoints.
- Prefer publisher/agency APIs, repository OAI-PMH, DOI metadata, and documented open-data endpoints.
- Respect robots rules, terms, rate limits, copyright, licenses, and institutional access controls.
- Never bypass paywalls, authentication, or access controls.
- Do not execute downloaded code, notebooks, macros, binaries, or embedded scripts during ingestion.
- Parse in resource-limited workers; quarantine malformed or suspicious files.
- Preserve original files only where the license permits; otherwise store permitted metadata and a lawful link.
- Mark every catalog seed as unverified until the institution/domain and endpoint are reviewed.

## 5. Deduplication and novelty

Deduplicate in stages:

1. exact artifact SHA-256;
2. DOI, repository accession, or publisher identifier;
3. normalized title + authors + year;
4. near-duplicate text and abstract similarity;
5. claim-level semantic overlap.

Do not delete legitimate distinct editions or contradictory studies. Link preprint, accepted manuscript, publisher version, dataset, thesis, and later correction as related records. Novelty is a review label, not a model-generated certainty: classify additions as new region, new observation, new method, replication, reinterpretation, correction, or duplicate.

## 6. Cross-language handling

Retain original language and script. Store translations as derivative records with model/tool, version, date, and quality status. Scientific names, stratigraphic units, mineral names, symbols, coordinates, units, and citations must be preserved and normalized without overwriting the original. For Russian and Chinese sources, require terminology review for high-impact claims; Arabic and French sources receive the same evidence treatment.

## 7. Retrieval and answer policy

At answer time, retrieve by topic, spatial overlap, geological time, method, source authority, and evidence quality. Rerank by relevance and provenance completeness. Ali should provide:

- a concise answer;
- cited evidence and exact locators;
- distinction between observation and interpretation;
- conflicting evidence when material;
- uncertainty and coverage limits;
- data or tests needed to resolve remaining uncertainty.

A citation must resolve to the source record and not merely to an institution homepage.

## 8. Training policy

Do not fine-tune until the retrieval system and evaluation set are established.

Training candidates must be:
- license-reviewed and provenance-complete;
- deduplicated and separated by source/work;
- split by publication or geological region to reduce leakage;
- checked for benchmark contamination;
- reviewed by geoscience subject matter experts for high-risk tasks.

Train on behavior and task formats (evidence extraction, citation discipline, uncertainty, unit/CRS checks, tool selection), not on a goal of memorizing entire reference libraries. Retrieval remains the source of current, auditable knowledge.

## 9. Acceptance gates

Before enabling Ali against production user datasets:

- source catalog endpoints and licenses reviewed;
- ingestion is bounded, observable, resumable, and safe;
- every answer citation resolves to evidence;
- deduplication preserves distinct scientific works;
- evaluation includes Arabic, English, Russian, Chinese, and French cases;
- withheld tests measure citation correctness, factuality, uncertainty, and regional coverage;
- no model training or data redistribution occurs without documented rights;
- scientific workflows remain disabled until each tool/engine has its own validation and safety gate.

## 10. Initial implementation boundary

The accompanying `ali_geoscience_source_catalog.json` is a small discovery seed. It contains institution homepages, not harvested papers or validated datasets. Entries marked `seed_homepage_unverified` require manual domain verification. No crawler, vector database, knowledge graph, Ali agent runtime, or fine-tuning pipeline is enabled by this commit.

## 10. Source review states and evidence types

License review and scientific review are separate fields. A source may be legally eligible for local indexing while its scientific content remains unassessed.

Each indexed document records:
- source_kind: research article, review article, official dataset, technical report, textbook, field observation, core note, preprint, or other;
- scientific_review_status: not_assessed (default), editorial_reviewed, or subject_matter_reviewed;
- scientific reviewer and review date when a review status is claimed.

A completed scientific review status requires a reviewer identity and a real calendar date. The metadata records that a review was declared; it does not independently prove peer review, source authority, correctness, or claim-level validation. Search results expose these fields so Ali can avoid treating all retrieved sources as equivalent. Existing local databases migrate with the conservative default not_assessed.

## 11. Local retrieval foundation implemented

The application now has a small SQLite knowledge index:

- Stores reviewed source metadata, file SHA-256, original language, license basis, reviewer, and review date.
- Splits local UTF-8 text into bounded chunks with overlap.
- Deduplicates by stable source ID and exact file digest.
- Uses SQLite FTS5 when available and a parameterized token-scan fallback on SQLite builds without FTS5. Each hit reports exact matched query tokens, lexical coverage, and an explicit lexical-only evidence label; substring-only fallback matches are discarded. The response also aggregates matched terms, maximum coverage across the returned top results, and citable-hit count. The summary is explicitly scoped to returned results and never represents scientific confidence.
- Provides local status and search endpoints and attaches up to three retrieved source chunks to an identified analysis plan.
- Does not use embedding vectors, model weights, remote inference, or automatic downloads.

Ingestion is deliberately explicit through `geologia-knowledge`. The operator must supply the source ID, title, original language, license name, accepted license status, reviewer, review date, and optionally a stable HTTPS URL or DOI. UTF-8 `.txt`, `.md`, `.csv`, and `.json` files are accepted, along with local text-based PDF files through the lightweight optional `pypdf` extra. The per-file limit is 20 MiB; PDFs are limited to 500 pages, 200,000 extracted characters per page, and 5,000,000 characters total; each extracted chunk retains a PDF page locator. Scanned-image OCR, password-protected PDFs, automatic downloads, and remote extraction are not included. The install scripts and desktop build include the PDF extra; manual base installs may add it with `python -m pip install 'geologia[pdf]'.

The retrieval endpoints are:

- `GET /api/v1/knowledge/status`
- `GET /api/v1/knowledge/search?q=...`

Analysis plans report retrieval status and source metadata, but do not convert retrieved text into a validated scientific conclusion. A citation points to a local indexed text chunk; original page/section locators are not inferred.

**Current corpus status:** the index automatically seeds 24 original GEOLOGIA-authored checklists in Arabic, English, Russian, and Chinese on first search/status. The external research corpus remains empty until an operator explicitly ingests lawful local text. The institution catalog remains discovery metadata and the approved bibliographic registry is still empty; no full-text publications have been automatically downloaded or ingested.

## 11. Built-in core knowledge pack

The package contains 24 original GEOLOGIA-authored checklists: six domains in Arabic, English, Russian, and Chinese (groundwater, GIS/CRS, 3D geology, seismology, remote sensing, and mineral exploration). The local index seeds them on first search/status and deduplicates by stable source ID. The notes are licensed as repository original content and link to authoritative source pages; they do not reproduce external publication text.

This is **retrieval memory**, not neural training. The agent retrieves relevant local chunks and their source metadata; it does not infer a scientific result from a checklist. External documents remain subject to explicit license review and ingestion. The FTS index uses schema v2 with deterministic CJK bigram tokens; it rebuilds from preserved original chunks during migration, so Chinese queries can match without embeddings or model weights.

See [ALI_SOURCE_LICENSE_MATRIX.md](ALI_SOURCE_LICENSE_MATRIX.md) for the reviewed international source families and ingestion restrictions.

## Claim-to-evidence annotation ledger

GEOLOGIA now provides a local ledger for explicitly recording a human-authored claim and linking it to exact indexed evidence chunks. Each link must be labelled `supports`, `contradicts`, `contextualizes`, or `unclear`, and includes a rationale and recorder. Duplicate links are rejected. Claim records are not generated automatically by retrieval and are not automatically treated as scientific conclusions.

The API returns `scientific_validation: not_performed` for claim records and evidence annotations. A relation label is an attributed annotation, not proof of truth, causality, sufficiency, or consensus. The ledger preserves the exact chunk ID, source identity, source type, review state, license state, and locator for traceability. Future scientific review workflows must evaluate the actual claim, methods, uncertainty, and conflicting evidence before any validated conclusion can be represented.
