from contextlib import closing

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

    unsupported = local_index / "source.pdf"
    unsupported.write_bytes(b"not a pdf parser input")
    with pytest.raises(ValueError, match="only UTF-8"):
        knowledge.ingest_document(unsupported, metadata())


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


def test_core_seed_pack_is_bilingual_local_and_idempotent(tmp_path, monkeypatch):
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
    assert knowledge.status()["document_count"] == 12

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
    with knowledge._connect() as connection:
        assert knowledge._fts_available(connection)
        assert connection.execute(
            "SELECT value FROM knowledge_meta WHERE key = 'fts_schema_version'"
        ).fetchone()["value"] == "2"
        assert connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_fts'"
        ).fetchone() is None

    found = knowledge.search("geological mapping")
    assert any(item["source_id"] == "fts-migration-01" for item in found["results"])
