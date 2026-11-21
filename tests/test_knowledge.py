from contextlib import closing
import sqlite3

import pytest

from geologia import knowledge

@pytest.fixture


def local_index(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "application.sqlite3"))
    monkeypatch.delenv("GEOLOGIA_KNOWLEDGE_DB_PATH", raising=False)
    monkeypatch.setenv("GEOLOGIA_DISABLE_CORE_SEED", "1")
    knowledge.initialize()
    return tmp_path


def metadata(**overrides):
    values = {
        "source_id": "hydro-textbook-001",
        "title": "Groundwater and recharge",
        "author": "Research Group",
        "publisher": "Open Geoscience Archive",
        "source_url": "https://example.org/groundwater",
        "doi": "",
        "license_name": "CC BY 4.0",
        "license_status": "open_license",
        "reviewed_by": "local reviewer",
        "review_date": "2026-11-21",
        "language": "en",
        "source_kind": "textbook",
        "scientific_review_status": "not_assessed",
        "scientific_reviewed_by": "",
        "scientific_review_date": "",
    }
    values.update(overrides)
    return values


def test_chunking_is_bounded_and_overlaps_long_text():
    paragraph = "groundwater recharge aquifer stratigraphy " * 150
    chunks = knowledge.chunk_text(paragraph)
    assert len(chunks) > 1
    assert all(0 < len(chunk) <= knowledge.MAX_CHUNK_CHARS for chunk in chunks)
    assert chunks[0][-80:] in chunks[1]


def test_ingest_and_search_return_reviewed_citation_metadata(local_index):
    source = local_index / "source.md"
    source.write_text(
        "# Groundwater\n\nAquifer recharge and groundwater levels are measured "
        "with observation wells.\n\nHydrogeology uses a clear water balance.",
        encoding="utf-8",
    )
    result = knowledge.ingest_document(source, metadata())
    assert result["status"] == "indexed"
    assert result["chunk_count"] >= 1

    found = knowledge.search("aquifer recharge", limit=3)
    assert found["count"] >= 1
    assert found["model_used"] is False
    assert found["scientific_conclusion"] is False
    hit = found["results"][0]
    assert hit["source_id"] == "hydro-textbook-001"
    assert hit["license_status"] == "open_license"
    assert hit["source_url"] == "https://example.org/groundwater"
    assert hit["file_sha256"] == result["file_sha256"]
    assert hit["chunk_number"] >= 1
    assert "local indexed text chunk" in hit["citation_locator"]


def test_duplicate_source_and_file_are_idempotent(local_index):
    source = local_index / "same.txt"
    source.write_text("Groundwater data and aquifer recharge.", encoding="utf-8")
    first = knowledge.ingest_document(source, metadata())
    second = knowledge.ingest_document(source, metadata())
    assert first["status"] == "indexed"
    assert second["status"] == "already_indexed"
    assert second["document_id"] == first["document_id"]
    assert knowledge.status()["document_count"] == 1


def test_ingestion_rejects_unreviewed_license_status(local_index):
    source = local_index / "unreviewed.txt"
    source.write_text("Geology reference text.", encoding="utf-8")
    with pytest.raises(ValueError, match="license_status"):
        knowledge.ingest_document(source, metadata(license_status="unverified"))
    assert knowledge.status()["document_count"] == 0


def test_ingestion_rejects_invalid_utf8_and_unsupported_extension(local_index):
    invalid = local_index / "invalid.txt"
    invalid.write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="UTF-8"):
        knowledge.ingest_document(invalid, metadata())

    unsupported = local_index / "source.bin"
    unsupported.write_bytes(b"not a pdf parser input")
    with pytest.raises(ValueError, match="only UTF-8"):
        knowledge.ingest_document(unsupported, metadata())


def test_ingestion_rejects_oversized_file_before_parsing(local_index):
    source = local_index / "oversized.pdf"
    with source.open("wb") as output:
        output.truncate(knowledge.MAX_SOURCE_BYTES + 1)
    with pytest.raises(ValueError, match="20 MiB"):
        knowledge.ingest_document(source, metadata(source_id="oversized-pdf-001"))


def test_search_rejects_empty_and_overlong_queries(local_index):
    with pytest.raises(ValueError, match="searchable text"):
        knowledge.search("   ")
    with pytest.raises(ValueError, match="500 character"):
        knowledge.search("x" * 501)


def test_status_reports_local_model_free_storage(local_index):
    status = knowledge.status()
    assert status["storage"] == "local_sqlite"
    assert status["document_count"] == 0
    assert status["model_required"] is False
    assert status["network_required"] is False
    assert status["automatic_downloads_enabled"] is False


def test_open_license_ingestion_rejects_noncommercial_and_no_derivatives_terms(
    local_index,
):
    source = local_index / "restricted.txt"
    source.write_text("Restricted source text.", encoding="utf-8")
    with pytest.raises(ValueError, match="non-commercial or no-derivatives"):
        knowledge.ingest_document(
            source,
            metadata(license_name="CC BY-NC-ND 4.0", license_status="open_license"),
        )


def test_core_seed_pack_is_four_language_local_and_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "core.sqlite3"))
    monkeypatch.delenv("GEOLOGIA_KNOWLEDGE_DB_PATH", raising=False)
    monkeypatch.delenv("GEOLOGIA_DISABLE_CORE_SEED", raising=False)

    first_status = knowledge.status()
    assert first_status["document_count"] == len(knowledge.CORE_SEEDS)
    assert first_status["core_seed_count"] == len(knowledge.CORE_SEEDS)
    assert first_status["core_seeded_count"] == len(knowledge.CORE_SEEDS)
    assert first_status["core_seeded_automatically"] is True

    found = knowledge.search("المياه الجوفية", limit=10)
    assert found["count"] > 0
    assert any(
        item["source_id"] == "geologia-core-hydrology-ar-v1"
        for item in found["results"]
    )
    second_status = knowledge.status()
    assert second_status["document_count"] == len(knowledge.CORE_SEEDS)
    assert second_status["network_required"] is False

    russian = knowledge.search("подземные воды", limit=10)
    assert any(
        item["source_id"] == "geologia-core-hydrology-ru-v1"
        for item in russian["results"]
    )
    chinese = knowledge.search("地下水", limit=10)
    assert any(
        item["source_id"] == "geologia-core-hydrology-zh-v1"
        for item in chinese["results"]
    )


def test_doi_deduplication_prevents_duplicate_bibliographic_work(local_index):
    first_source = local_index / "first.txt"
    second_source = local_index / "second.txt"
    first_source.write_text("Original DOI source text.", encoding="utf-8")
    second_source.write_text("A different local extraction of the same DOI.", encoding="utf-8")
    first = knowledge.ingest_document(
        first_source,
        metadata(source_id="doi-source-a", doi="10.1234/geo.1"),
    )
    second = knowledge.ingest_document(
        second_source,
        metadata(source_id="doi-source-b", doi="https://doi.org/10.1234/geo.1"),
    )
    assert first["status"] == "indexed"
    assert second["status"] == "already_indexed"
    assert second["duplicate_reason"] == "doi"
    assert knowledge.status()["document_count"] == 1


def test_knowledge_cli_can_seed_core_pack(tmp_path, monkeypatch, capsys):
    from geologia.knowledge_cli import main

    monkeypatch.setenv("GEOLOGIA_DB_PATH", str(tmp_path / "cli.sqlite3"))
    monkeypatch.delenv("GEOLOGIA_KNOWLEDGE_DB_PATH", raising=False)
    monkeypatch.delenv("GEOLOGIA_DISABLE_CORE_SEED", raising=False)
    main(["--seed-core"])
    output = capsys.readouterr().out
    assert '"source_count": 24' in output
    assert '"external_downloads": 0' in output
    assert knowledge.status()["document_count"] == 24


def test_cjk_bigrams_enable_chinese_text_retrieval(local_index):
    source = local_index / "chinese_geo.txt"
    source.write_text("地质灾害遥感监测与机器学习。地下水资源评价。", encoding="utf-8")
    knowledge.ingest_document(
        source,
        metadata(source_id="zh-geology-01", title="地质与地下水", language="zh"),
    )
    assert "地下" in knowledge._query_tokens("地下水")
    assert "下水" in knowledge._query_tokens("地下水")
    result = knowledge.search("地下水")
    assert any(item["source_id"] == "zh-geology-01" for item in result["results"])


def test_fts_v2_rebuilds_legacy_index_and_preserves_chunks(local_index):
    source = local_index / "migration.md"
    source.write_text("Geological mapping and groundwater records.", encoding="utf-8")
    knowledge.ingest_document(source, metadata(source_id="fts-migration-01"))

    with closing(knowledge._connect()) as connection:
        if not knowledge._fts_available(connection):
            pytest.skip("SQLite FTS5 is not available in this environment")
        connection.execute("DROP TABLE knowledge_fts_v2")
        connection.execute(
            "CREATE VIRTUAL TABLE knowledge_fts USING fts5("
            "chunk_id UNINDEXED, title, body, tokenize='unicode61')"
        )
        connection.execute(
            "DELETE FROM knowledge_meta WHERE key = 'fts_schema_version'"
        )
        connection.commit()

    knowledge.initialize()
    with closing(knowledge._connect()) as connection:
        assert knowledge._fts_available(connection)
        assert connection.execute(
            "SELECT value FROM knowledge_meta WHERE key = 'fts_schema_version'"
        ).fetchone()["value"] == "2"
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_fts'"
        ).fetchone() is None

    found = knowledge.search("geological mapping")
    assert any(item["source_id"] == "fts-migration-01" for item in found["results"])


def _write_text_pdf(path, page_texts):
    pytest.importorskip("pypdf")
    from pypdf import PdfWriter
    from pypdf.generic import (
        DecodedStreamObject,
        DictionaryObject,
        NameObject,
    )

    writer = PdfWriter()
    for text in page_texts:
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
        font_ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
        })
        escaped = text
        stream = DecodedStreamObject()
        stream.set_data(
            f"BT /F1 12 Tf 50 700 Td ({escaped}) Tj ET".encode("ascii")
        )
        page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as output:
        writer.write(output)


def test_pdf_ingestion_preserves_page_citation_locator(local_index):
    source = local_index / "field_reference.pdf"
    _write_text_pdf(
        source,
        ["Groundwater aquifer observation wells", "Fracture mapping and structural geology"],
    )
    result = knowledge.ingest_document(
        source,
        metadata(source_id="pdf-reference-001", title="Field reference PDF"),
    )
    assert result["status"] == "indexed"
    assert result["pages_extracted"] == 2
    assert result["chunk_count"] == 2

    found = knowledge.search("fracture mapping", limit=5)
    hit = next(item for item in found["results"]
                if item["source_id"] == "pdf-reference-001")
    assert hit["citation_locator"] == "PDF page 2, text chunk 1"
    assert "Fracture mapping" in hit["excerpt"]


def test_pdf_rejects_scanned_images_without_ocr_claim(local_index):
    source = local_index / "scanned.pdf"
    _write_text_pdf(source, [""])
    with pytest.raises(ValueError, match="no extractable text"):
        knowledge.ingest_document(source, metadata(source_id="pdf-scan-001"))


def test_source_locator_schema_migrates_existing_text_chunks(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setenv("GEOLOGIA_KNOWLEDGE_DB_PATH", str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "CREATE TABLE knowledge_chunks (chunk_id TEXT PRIMARY KEY, "
            "document_id TEXT NOT NULL, chunk_index INTEGER NOT NULL, body TEXT NOT NULL, "
            "UNIQUE(document_id, chunk_index))"
        )
        connection.execute(
            "INSERT INTO knowledge_chunks(chunk_id,document_id,chunk_index,body) "
            "VALUES('old-chunk','old-document',0,'old text')"
        )

    knowledge.initialize()
    with closing(knowledge._connect()) as connection:
        row = connection.execute(
            "SELECT source_locator FROM knowledge_chunks WHERE chunk_id='old-chunk'"
        ).fetchone()
    assert row["source_locator"] == "local indexed text chunk 1"

def test_pdf_extraction_rejects_single_page_text_beyond_limit(local_index, monkeypatch):
    source = local_index / "large_page.pdf"
    _write_text_pdf(source, ["A" * 120])
    monkeypatch.setattr(knowledge, "MAX_PDF_PAGE_TEXT_CHARS", 100)
    with pytest.raises(ValueError, match="page 1 exceeds"):
        knowledge.ingest_document(
            source, metadata(source_id="pdf-large-page-001")
        )


def test_pdf_extraction_rejects_total_text_beyond_limit(local_index, monkeypatch):
    source = local_index / "many_pages.pdf"
    _write_text_pdf(source, ["A" * 40, "B" * 40, "C" * 40])
    monkeypatch.setattr(knowledge, "MAX_PDF_PAGE_TEXT_CHARS", 100)
    monkeypatch.setattr(knowledge, "MAX_PDF_EXTRACTED_CHARS", 90)
    with pytest.raises(ValueError, match="total extracted-text"):
        knowledge.ingest_document(
            source, metadata(source_id="pdf-total-text-001")
        )

def test_token_scan_fallback_ranks_chunks_by_query_term_coverage(local_index, monkeypatch):
    multi = local_index / "multi.txt"
    single = local_index / "single.txt"
    multi.write_text(
        "Aquifer recharge is an important groundwater process.",
        encoding="utf-8",
    )
    single.write_text(
        "Aquifer properties are measured in field surveys.", encoding="utf-8"
    )
    knowledge.ingest_document(
        multi, metadata(source_id="rank-multi-001", title="Multi term")
    )
    knowledge.ingest_document(
        single, metadata(source_id="rank-single-001", title="Single term")
    )
    monkeypatch.setattr(knowledge, "_fts_available", lambda _connection: False)

    found = knowledge.search("aquifer recharge", limit=5)
    assert found["retrieval_method"] == "sqlite_token_scan"
    assert found["results"][0]["source_id"] == "rank-multi-001"
def test_evidence_chunk_ids_are_stable_across_local_indexes(
    tmp_path, monkeypatch
):
    source = tmp_path / "stable-source.txt"
    source.write_text(
        "Groundwater recharge and aquifer storage evidence.",
        encoding="utf-8",
    )
    ids = []
    for index_name in ("first.sqlite3", "second.sqlite3"):
        monkeypatch.setenv(
            "GEOLOGIA_KNOWLEDGE_DB_PATH", str(tmp_path / index_name)
        )
        monkeypatch.setenv("GEOLOGIA_DISABLE_CORE_SEED", "1")
        knowledge.ingest_document(
            source,
            metadata(source_id="stable-evidence-001", title="Stable evidence"),
        )
        with closing(knowledge._connect()) as connection:
            ids.append([
                row["chunk_id"]
                for row in connection.execute(
                    "SELECT chunk_id FROM knowledge_chunks ORDER BY chunk_index"
                )
            ])
    assert ids[0]
    assert ids[0] == ids[1]


def test_search_reports_exact_query_term_coverage_and_evidence(local_index):
    source = local_index / "coverage.txt"
    source.write_text(
        "Aquifer recharge supports groundwater replenishment.",
        encoding="utf-8",
    )
    knowledge.ingest_document(
        source, metadata(source_id="coverage-001", title="Aquifer recharge")
    )

    found = knowledge.search("aquifer recharge", limit=3)
    hit = next(item for item in found["results"] if item["source_id"] == "coverage-001")
    assert hit["matched_query_terms"] == ["aquifer", "recharge"]
    assert hit["query_term_coverage"] == 1.0
    assert hit["retrieval_evidence"] == "exact_lexical_tokens"


def test_token_fallback_does_not_accept_substring_only_matches(local_index, monkeypatch):
    source = local_index / "substring.txt"
    source.write_text("The shoreline is mapped during fieldwork.", encoding="utf-8")
    knowledge.ingest_document(
        source, metadata(source_id="substring-001", title="Shoreline mapping")
    )
    monkeypatch.setattr(knowledge, "_fts_available", lambda _connection: False)

    found = knowledge.search("ore", limit=5)
    assert all(item["source_id"] != "substring-001" for item in found["results"])


def test_search_summary_aggregates_returned_evidence_without_confidence_claim(local_index):
    source = local_index / "summary.txt"
    source.write_text(
        "Aquifer recharge and groundwater replenishment are studied.",
        encoding="utf-8",
    )
    knowledge.ingest_document(
        source, metadata(source_id="summary-001", title="Aquifer recharge")
    )

    found = knowledge.search("aquifer recharge absent", limit=3)
    summary = found["evidence_summary"]
    assert summary["query_token_count"] == 3
    assert summary["matched_query_terms"] == ["aquifer", "recharge"]
    assert summary["maximum_query_term_coverage"] == pytest.approx(2 / 3, abs=0.0001)
    assert summary["coverage_scope"] == "returned_results"
    assert summary["coverage_interpretation"] == (
        "lexical_match_only_not_scientific_confidence"
    )
    assert summary["citable_result_count"] >= 1
    assert found["scientific_conclusion"] is False


def test_empty_search_results_have_zero_evidence_summary(local_index):
    found = knowledge.search("unmatched volcanology phrase", limit=3)
    summary = found["evidence_summary"]
    assert found["count"] == 0
    assert summary["matched_query_terms"] == []
    assert summary["maximum_query_term_coverage"] == 0.0
    assert summary["citable_result_count"] == 0

def test_knowledge_cli_search_returns_local_evidence_summary(local_index, capsys):
    from geologia.knowledge_cli import main

    source = local_index / "cli-search.md"
    source.write_text(
        "Aquifer recharge supports groundwater replenishment.",
        encoding="utf-8",
    )
    knowledge.ingest_document(
        source, metadata(source_id="cli-search-001", title="Aquifer recharge")
    )

    main(["--search", "aquifer recharge", "--limit", "3"])
    output = capsys.readouterr().out
    import json
    result = json.loads(output)

    assert result["count"] >= 1
    assert result["model_used"] is False
    assert result["evidence_summary"]["matched_query_terms"] == [
        "aquifer", "recharge"
    ]
    assert result["results"][0]["source_id"] == "cli-search-001"


def test_knowledge_cli_accepts_scientific_review_metadata(tmp_path, monkeypatch, capsys):
    from geologia.knowledge_cli import main
    import json

    monkeypatch.setenv("GEOLOGIA_KNOWLEDGE_DB_PATH", str(tmp_path / "cli-review.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_DISABLE_CORE_SEED", "1")
    source = tmp_path / "cli-reviewed.md"
    source.write_text("Geological evidence from a reviewed source.", encoding="utf-8")
    main([
        str(source),
        "--source-id", "cli-review-001",
        "--title", "Reviewed geology source",
        "--language", "en",
        "--license-name", "CC BY 4.0",
        "--license-status", "open_license",
        "--reviewed-by", "rights reviewer",
        "--review-date", "2026-11-21",
        "--source-kind", "research_article",
        "--scientific-review-status", "subject_matter_reviewed",
        "--scientific-reviewed-by", "Geoscience specialist",
        "--scientific-review-date", "2026-11-21",
    ])
    result = json.loads(capsys.readouterr().out)
    assert result["source_kind"] == "research_article"
    assert result["scientific_review_status"] == "subject_matter_reviewed"


def test_scientific_review_metadata_is_separate_from_license_review(local_index):
    source = local_index / "review-status.txt"
    source.write_text("A locally indexed geology source.", encoding="utf-8")
    result = knowledge.ingest_document(source, metadata())
    found = knowledge.search("geology source", limit=3)
    hit = next(item for item in found["results"]
                if item["source_id"] == "hydro-textbook-001")
    assert result["license_status"] == "open_license"
    assert hit["source_kind"] == "textbook"
    assert hit["scientific_review_status"] == "not_assessed"
    assert hit["scientific_reviewed_by"] is None
    assert hit["scientific_review_date"] is None


def test_scientific_review_requires_reviewer_and_valid_date(local_index):
    source = local_index / "reviewed-source.txt"
    source.write_text("A geology source reviewed by a specialist.", encoding="utf-8")
    incomplete = metadata(
        scientific_review_status="subject_matter_reviewed",
        scientific_reviewed_by="",
        scientific_review_date="",
    )
    with pytest.raises(ValueError, match="requires reviewer and date"):
        knowledge.ingest_document(source, incomplete)
    reviewed = metadata(
        scientific_review_status="subject_matter_reviewed",
        scientific_reviewed_by="Geoscience reviewer",
        scientific_review_date="2026-11-21",
    )
    result = knowledge.ingest_document(source, reviewed)
    assert result["scientific_review_status"] == "subject_matter_reviewed"


def test_scientific_review_date_rejects_invalid_calendar_date(local_index):
    source = local_index / "invalid-review-date.txt"
    source.write_text("Source with invalid review date.", encoding="utf-8")
    with pytest.raises(ValueError, match="real calendar date"):
        knowledge.ingest_document(
            source,
            metadata(
                scientific_review_status="editorial_reviewed",
                scientific_reviewed_by="Editorial reviewer",
                scientific_review_date="2026-02-31",
            ),
        )



def test_knowledge_documents_migrate_scientific_review_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "old-knowledge.sqlite3"
    monkeypatch.setenv("GEOLOGIA_KNOWLEDGE_DB_PATH", str(db_path))
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE knowledge_documents (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL, title TEXT NOT NULL,
                author TEXT, publisher TEXT, source_url TEXT, doi TEXT,
                license_name TEXT NOT NULL, license_status TEXT NOT NULL,
                reviewed_by TEXT NOT NULL, review_date TEXT NOT NULL,
                language TEXT NOT NULL, filename TEXT NOT NULL,
                file_sha256 TEXT NOT NULL, indexed_at TEXT NOT NULL,
                UNIQUE(source_id, file_sha256)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO knowledge_documents VALUES (
                'legacy-doc', 'legacy-source', 'Legacy source', NULL, NULL, NULL,
                NULL, 'CC BY 4.0', 'open_license', 'license reviewer',
                '2026-11-21', 'en', 'legacy.txt', 'abc123', '2026-11-21T00:00:00Z'
            )
            """
        )
    knowledge.initialize()
    with closing(knowledge._connect()) as connection:
        row = connection.execute(
            "SELECT source_kind, scientific_review_status, "
            "scientific_reviewed_by, scientific_review_date "
            "FROM knowledge_documents WHERE id='legacy-doc'"
        ).fetchone()
    assert row["source_kind"] == "other"
    assert row["scientific_review_status"] == "not_assessed"
    assert row["scientific_reviewed_by"] is None
    assert row["scientific_review_date"] is None


def test_claim_evidence_ledger_records_relations_without_scientific_validation(local_index):
    source = local_index / "evidence.txt"
    source.write_text(
        "Recharge increases groundwater levels under the documented conditions.",
        encoding="utf-8",
    )
    knowledge.ingest_document(source, metadata())
    search = knowledge.search("recharge groundwater levels", limit=3)
    chunk_id = search["results"][0]["chunk_id"]
    claim = knowledge.create_claim(
        "Groundwater levels increased after recharge.",
        "field geologist",
    )
    annotation = knowledge.annotate_claim_evidence(
        claim["claim_id"],
        chunk_id,
        "supports",
        "The indexed passage explicitly describes an increase under stated conditions.",
        "reviewer A",
    )
    readback = knowledge.get_claim(claim["claim_id"])
    assert claim["scientific_validation"] == "not_performed"
    assert annotation["relation"] == "supports"
    assert readback["scientific_validation"] == "not_performed"
    assert readback["evidence_count"] == 1
    assert readback["evidence_annotations"][0]["chunk_id"] == chunk_id
    assert "do not establish truth" in readback["interpretation"]


def test_claim_evidence_rejects_missing_claim_chunk_and_duplicate(local_index):
    source = local_index / "evidence-2.txt"
    source.write_text("A measured geological observation for testing.", encoding="utf-8")
    knowledge.ingest_document(source, metadata())
    chunk_id = knowledge.search("measured geological observation", limit=1)["results"][0]["chunk_id"]
    claim = knowledge.create_claim("A testable geological statement.", "researcher")
    with pytest.raises(ValueError, match="claim_id does not exist"):
        knowledge.annotate_claim_evidence(
            "missing-claim", chunk_id, "supports", "Reason", "reviewer"
        )
    with pytest.raises(ValueError, match="chunk_id does not exist"):
        knowledge.annotate_claim_evidence(
            claim["claim_id"], "missing-chunk", "supports", "Reason", "reviewer"
        )
    knowledge.annotate_claim_evidence(
        claim["claim_id"], chunk_id, "supports", "Reason", "reviewer"
    )
    with pytest.raises(ValueError, match="already linked"):
        knowledge.annotate_claim_evidence(
            claim["claim_id"], chunk_id, "contradicts", "Another reason", "reviewer"
        )


def test_claim_api_requires_explicit_relation_and_returns_unvalidated_claim(
    tmp_path, monkeypatch
):
    from fastapi.testclient import TestClient
    from geologia.api import app

    monkeypatch.setenv("GEOLOGIA_KNOWLEDGE_DB_PATH", str(tmp_path / "claims.sqlite3"))
    monkeypatch.setenv("GEOLOGIA_DISABLE_CORE_SEED", "1")
    source = tmp_path / "api-evidence.md"
    source.write_text("Groundwater recharge can affect observed water levels.", encoding="utf-8")
    knowledge.ingest_document(source, metadata(source_id="api-claim-source"))
    chunk_id = knowledge.search("groundwater recharge water levels", limit=1)["results"][0]["chunk_id"]
    client = TestClient(app)
    created = client.post(
        "/api/v1/knowledge/claims",
        json={"statement": "Recharge affected the measured water level.", "created_by": "analyst"},
    )
    assert created.status_code == 201
    claim_id = created.json()["claim_id"]
    bad = client.post(
        f"/api/v1/knowledge/claims/{claim_id}/evidence",
        json={"chunk_id": chunk_id, "relation": "proves", "rationale": "It proves it.", "recorded_by": "analyst"},
    )
    assert bad.status_code == 422
    linked = client.post(
        f"/api/v1/knowledge/claims/{claim_id}/evidence",
        json={"chunk_id": chunk_id, "relation": "contextualizes", "rationale": "Relevant context only.", "recorded_by": "analyst"},
    )
    assert linked.status_code == 201
    fetched = client.get(f"/api/v1/knowledge/claims/{claim_id}")
    assert fetched.status_code == 200
    assert fetched.json()["scientific_validation"] == "not_performed"
