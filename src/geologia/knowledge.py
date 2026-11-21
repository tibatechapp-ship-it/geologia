"""Small, local, license-reviewed text retrieval index for GEOLOGIA.

Uses Python's SQLite and optionally its built-in FTS5 extension. No embeddings,
model weights, remote APIs, automatic downloads, or source-code execution.
"""
from contextlib import closing
from datetime import date, datetime, timezone
from io import BytesIO
import hashlib
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlparse
from uuid import uuid4

MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_PDF_PAGE_TEXT_CHARS = 200_000
MAX_PDF_EXTRACTED_CHARS = 5_000_000
MAX_CHUNK_CHARS = 1600
CHUNK_OVERLAP_CHARS = 180
MAX_QUERY_CHARS = 500
MAX_QUERY_TOKENS = 12
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".pdf"}
LICENSE_STATUSES = {
    "public_domain", "open_license", "permission", "original_work"
}

CORE_SEEDS = [
    ("hydrology_en.md", "geologia-core-hydrology-en-v1", "Groundwater data readiness", "en"),
    ("hydrology_ar.md", "geologia-core-hydrology-ar-v1", "جاهزية بيانات المياه الجوفية", "ar"),
    ("hydrology_ru.md", "geologia-core-hydrology-ru-v1", "Гидрогеология — готовность данных", "ru"),
    ("hydrology_zh.md", "geologia-core-hydrology-zh-v1", "水文地质数据准备", "zh"),
    ("gis_crs_en.md", "geologia-core-gis-crs-en-v1", "GIS and CRS preflight", "en"),
    ("gis_crs_ar.md", "geologia-core-gis-crs-ar-v1",
     "فحص نظم المعلومات الجغرافية والإحداثيات", "ar"),
    ("gis_crs_ru.md", "geologia-core-gis-crs-ru-v1", "ГИС и системы координат", "ru"),
    ("gis_crs_zh.md", "geologia-core-gis-crs-zh-v1", "GIS 与坐标参考系统", "zh"),
    ("geology3d_en.md", "geologia-core-geology3d-en-v1", "3D geological modeling evidence", "en"),
    ("geology3d_ar.md", "geologia-core-geology3d-ar-v1",
     "أدلة النمذجة الجيولوجية ثلاثية الأبعاد", "ar"),
    ("geology3d_ru.md", "geologia-core-geology3d-ru-v1", "3D геологическое моделирование", "ru"),
    ("geology3d_zh.md", "geologia-core-geology3d-zh-v1", "三维地质建模", "zh"),
    ("seismology_en.md", "geologia-core-seismology-en-v1", "Seismology data quality", "en"),
    ("seismology_ar.md", "geologia-core-seismology-ar-v1", "جودة بيانات الزلازل", "ar"),
    ("seismology_ru.md", "geologia-core-seismology-ru-v1", "Сейсмология — качество данных", "ru"),
    ("seismology_zh.md", "geologia-core-seismology-zh-v1", "地震学数据质量", "zh"),
    ("remote_sensing_en.md", "geologia-core-remote-sensing-en-v1",
     "Remote sensing product readiness", "en"),
    ("remote_sensing_ar.md", "geologia-core-remote-sensing-ar-v1",
     "جاهزية منتجات الاستشعار عن بعد", "ar"),
    ("remote_sensing_ru.md", "geologia-core-remote-sensing-ru-v1",
     "Дистанционное зондирование — готовность данных", "ru"),
    ("remote_sensing_zh.md", "geologia-core-remote-sensing-zh-v1", "遥感产品准备", "zh"),
    ("mineral_exploration_en.md", "geologia-core-mineral-exploration-en-v1",
     "Mineral exploration QA/QC", "en"),
    ("mineral_exploration_ar.md", "geologia-core-mineral-exploration-ar-v1",
     "ضبط جودة استكشاف المعادن", "ar"),
    ("mineral_exploration_ru.md", "geologia-core-mineral-exploration-ru-v1",
     "Поиск полезных ископаемых — QA/QC", "ru"),
    ("mineral_exploration_zh.md", "geologia-core-mineral-exploration-zh-v1",
     "矿产勘查质量控制", "zh"),
]
CORE_SEED_DIR = Path(__file__).parent / "data" / "knowledge_seed"


def database_path() -> Path:
    configured = os.environ.get("GEOLOGIA_KNOWLEDGE_DB_PATH")
    if configured:
        return Path(configured).expanduser()
    application_db = Path(
        os.environ.get("GEOLOGIA_DB_PATH", ".geologia/geologia.sqlite3")
    ).expanduser()
    return application_db.parent / "knowledge.sqlite3"


def _connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


FTS_SCHEMA_VERSION = "2"
CJK_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def _cjk_bigrams(token: str) -> list[str]:
    return [token[index:index + 2] for index in range(len(token) - 1)]


def _fts_text(text: str) -> str:
    """Add CJK bigram tokens while retaining original words for FTS matching."""
    terms = []
    for token in re.findall(r"[\w]+", text, flags=re.UNICODE):
        if CJK_PATTERN.search(token):
            terms.append(token)
            terms.extend(_cjk_bigrams(token))
        else:
            terms.append(token)
    return " ".join(terms)


def _fts_available(connection: sqlite3.Connection) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' "
        "AND name = 'knowledge_fts_v2'"
    ).fetchone() is not None


def initialize() -> None:
    """Create local schema and migrate the optional FTS index to CJK-aware v2."""
    with closing(_connect()) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                author TEXT,
                publisher TEXT,
                source_url TEXT,
                doi TEXT,
                license_name TEXT NOT NULL,
                license_status TEXT NOT NULL CHECK (
                    license_status IN (
                        'public_domain', 'open_license', 'permission', 'original_work'
                    )
                ),
                reviewed_by TEXT NOT NULL,
                review_date TEXT NOT NULL,
                language TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_sha256 TEXT NOT NULL,
                indexed_at TEXT NOT NULL,
                UNIQUE(source_id, file_sha256)
            );

            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                chunk_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES knowledge_documents(id),
                chunk_index INTEGER NOT NULL,
                body TEXT NOT NULL,
                source_locator TEXT NOT NULL DEFAULT '',
                UNIQUE(document_id, chunk_index)
            );

            CREATE TABLE IF NOT EXISTS knowledge_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document
                ON knowledge_chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_knowledge_documents_doi
                ON knowledge_documents(doi);
            """
        )
        chunk_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(knowledge_chunks)")
        }
        if "source_locator" not in chunk_columns:
            connection.execute(
                "ALTER TABLE knowledge_chunks ADD COLUMN source_locator TEXT NOT NULL DEFAULT ''"
            )
        connection.execute(
            "UPDATE knowledge_chunks SET source_locator = "
            "'local indexed text chunk ' || (chunk_index + 1) "
            "WHERE source_locator = ''"
        )
        fts_existed = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' "
            "AND name = 'knowledge_fts_v2'"
        ).fetchone() is not None
        try:
            connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts_v2 "
                "USING fts5(chunk_id UNINDEXED, title, body, tokenize='unicode61')"
            )
        except sqlite3.OperationalError:
            # Some mobile/system SQLite builds omit FTS5; token scan remains usable.
            connection.commit()
            return

        version = connection.execute(
            "SELECT value FROM knowledge_meta WHERE key = 'fts_schema_version'"
        ).fetchone()
        if not fts_existed or not version or version["value"] != FTS_SCHEMA_VERSION:
            connection.execute("DELETE FROM knowledge_fts_v2")
            chunks = connection.execute(
                """
                SELECT c.chunk_id, d.title, c.body
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.id = c.document_id
                ORDER BY d.title, c.chunk_index
                """
            ).fetchall()
            connection.executemany(
                "INSERT INTO knowledge_fts_v2 (chunk_id, title, body) VALUES (?, ?, ?)",
                [
                    (row["chunk_id"], _fts_text(row["title"]), _fts_text(row["body"]))
                    for row in chunks
                ],
            )
            connection.execute(
                "INSERT OR REPLACE INTO knowledge_meta (key, value) "
                "VALUES ('fts_schema_version', ?)",
                (FTS_SCHEMA_VERSION,),
            )
        old_fts = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'knowledge_fts'"
        ).fetchone()
        if old_fts:
            connection.execute("DROP TABLE knowledge_fts")
        connection.commit()


def _required_text(metadata: dict, key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required for local source attribution")
    return value.strip()


def _validate_metadata(metadata: dict) -> dict:
    source_id = _required_text(metadata, "source_id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{1,127}", source_id):
        raise ValueError("source_id must be a stable 2-128 character identifier")
    title = _required_text(metadata, "title")
    license_name = _required_text(metadata, "license_name")
    license_status = _required_text(metadata, "license_status")
    if license_status not in LICENSE_STATUSES:
        raise ValueError("license_status must represent a reviewed lawful source")
    if license_status == "open_license":
        compact_license = re.sub(r"[\s-]+", "", license_name.casefold())
        if (
            "noncommercial" in compact_license
            or "noderivatives" in compact_license
            or re.search(r"ccby(?:nc|nd)", compact_license)
        ):
            raise ValueError(
                "non-commercial or no-derivatives terms are not eligible for "
                "open_license ingestion; obtain explicit permission or keep metadata only"
            )
    reviewed_by = _required_text(metadata, "reviewed_by")
    review_date = _required_text(metadata, "review_date")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", review_date):
        raise ValueError("review_date must use YYYY-MM-DD")
    try:
        date.fromisoformat(review_date)
    except ValueError as exc:
        raise ValueError("review_date must be a real calendar date") from exc

    language = _required_text(metadata, "language").lower()
    if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*|und", language):
        raise ValueError("language must be a language code such as ar, en, ru, zh, or und")

    source_url = (metadata.get("source_url") or "").strip() or None
    if source_url:
        parsed = urlparse(source_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("source_url must be an HTTPS citation URL")

    doi = (metadata.get("doi") or "").strip() or None
    if doi:
        doi = re.sub(r"^https?://doi\.org/", "", doi, flags=re.IGNORECASE)
        doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
            raise ValueError("doi does not match the expected DOI form")

    return {
        "source_id": source_id,
        "title": title,
        "author": (metadata.get("author") or "").strip() or None,
        "publisher": (metadata.get("publisher") or "").strip() or None,
        "source_url": source_url,
        "doi": doi.lower() if doi else None,
        "license_name": license_name,
        "license_status": license_status,
        "reviewed_by": reviewed_by,
        "review_date": review_date,
        "language": language,
    }


def _split_long_paragraph(paragraph: str) -> list[str]:
    pieces = []
    start = 0
    while start < len(paragraph):
        end = min(start + MAX_CHUNK_CHARS, len(paragraph))
        if end < len(paragraph):
            boundary = paragraph.rfind(" ", start + MAX_CHUNK_CHARS // 2, end)
            if boundary > start:
                end = boundary
        piece = paragraph[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(paragraph):
            break
        start = max(start + 1, end - CHUNK_OVERLAP_CHARS)
    return pieces


def chunk_text(text: str) -> list[str]:
    """Split UTF-8 source text into bounded chunks while retaining overlap."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > MAX_CHUNK_CHARS:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_paragraph(paragraph))
            continue
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def _extract_pdf_pages(raw: bytes) -> list[tuple[int, str]]:
    """Extract text from a local PDF without OCR or network access."""
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:
        raise ValueError(
            "PDF indexing requires the optional 'pdf' extra: "
            "python -m pip install 'geologia[pdf]'"
        ) from exc

    try:
        reader = PdfReader(BytesIO(raw), strict=False)
        if reader.is_encrypted:
            raise ValueError(
                "encrypted PDFs are not supported; provide an authorized unencrypted copy"
            )
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF exceeds the {MAX_PDF_PAGES}-page indexing limit")
        pages = []
        extracted_total = 0
        for page_number, page in enumerate(reader.pages, start=1):
            extracted = page.extract_text() or ""
            if len(extracted) > MAX_PDF_PAGE_TEXT_CHARS:
                raise ValueError(
                    f"PDF page {page_number} exceeds the "
                    f"{MAX_PDF_PAGE_TEXT_CHARS}-character extraction limit"
                )
            extracted = extracted.replace("\r\n", "\n").replace("\r", "\n").strip()
            extracted_total += len(extracted)
            if extracted_total > MAX_PDF_EXTRACTED_CHARS:
                raise ValueError(
                    "PDF exceeds the total extracted-text character limit"
                )
            if extracted:
                pages.append((page_number, extracted))
    except ValueError:
        raise
    except (PdfReadError, OSError, EOFError, KeyError, TypeError) as exc:
        raise ValueError("could not safely parse or extract text from this PDF") from exc

    if not pages:
        raise ValueError(
            "PDF contains no extractable text; scanned-image OCR is not included "
            "in the lightweight core"
        )
    return pages


def ingest_document(path: str | Path, metadata: dict) -> dict:
    """Index a local UTF-8 text or PDF document after explicit license review."""
    source_path = Path(path).expanduser()
    suffix = source_path.suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("only UTF-8 .txt, .md, .csv, .json, and .pdf files can be indexed")
    if not source_path.is_file():
        raise ValueError("source file does not exist or is not a regular file")

    try:
        if source_path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("source file exceeds the 20 MiB local indexing limit")
        with source_path.open("rb") as source_file:
            raw = source_file.read(MAX_SOURCE_BYTES + 1)
    except OSError as exc:
        raise ValueError("could not read the local source file") from exc
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("source file exceeds the 20 MiB local indexing limit")
    if not raw:
        raise ValueError("source file is empty")

    indexed_chunks: list[tuple[str, str]] = []
    pages_extracted = None
    if suffix == ".pdf":
        pages = _extract_pdf_pages(raw)
        pages_extracted = len(pages)
        for page_number, page_text in pages:
            for chunk_number, body in enumerate(chunk_text(page_text), start=1):
                indexed_chunks.append(
                    (body, f"PDF page {page_number}, text chunk {chunk_number}")
                )
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("source text must be UTF-8") from exc
        if "\x00" in text:
            raise ValueError("source text contains NUL bytes")
        text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            raise ValueError("source text contains no indexable content")
        indexed_chunks = [
            (body, f"local indexed text chunk {index + 1}")
            for index, body in enumerate(chunk_text(text))
        ]

    if not indexed_chunks:
        raise ValueError("source text produced no searchable chunks")
    source = _validate_metadata(metadata)
    digest = hashlib.sha256(raw).hexdigest()
    document_id = uuid4().hex
    indexed_at = datetime.now(timezone.utc).isoformat()
    initialize()

    with closing(_connect()) as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            """
            SELECT id, source_id, file_sha256, doi
            FROM knowledge_documents
            WHERE (source_id = ? AND file_sha256 = ?)
               OR (? IS NOT NULL AND lower(doi) = lower(?))
            LIMIT 1
            """,
            (source["source_id"], digest, source["doi"], source["doi"]),
        ).fetchone()
        if existing:
            connection.rollback()
            return {
                "status": "already_indexed",
                "document_id": existing["id"],
                "source_id": source["source_id"],
                "file_sha256": digest,
                "chunk_count": connection.execute(
                    "SELECT count(*) FROM knowledge_chunks WHERE document_id = ?",
                    (existing["id"],),
                ).fetchone()[0],
                "duplicate_reason": (
                    "source_id_and_sha256"
                    if existing["source_id"] == source["source_id"]
                    and existing["file_sha256"] == digest
                    else "doi"
                ),
            }

        connection.execute(
            """
            INSERT INTO knowledge_documents (
                id, source_id, title, author, publisher, source_url, doi,
                license_name, license_status, reviewed_by, review_date,
                language, filename, file_sha256, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id, source["source_id"], source["title"], source["author"],
                source["publisher"], source["source_url"], source["doi"],
                source["license_name"], source["license_status"], source["reviewed_by"],
                source["review_date"], source["language"], source_path.name, digest,
                indexed_at,
            ),
        )
        has_fts = _fts_available(connection)
        for index, (body, locator) in enumerate(indexed_chunks):
            # Evidence identifiers remain stable across independent local indexes
            # when the reviewed source artifact and extracted chunk are identical.
            identity = (
                f"{source['source_id']}\\0{digest}\\0{index}\\0{body}"
            ).encode("utf-8")
            chunk_id = hashlib.sha256(identity).hexdigest()[:32]
            connection.execute(
                "INSERT INTO knowledge_chunks "
                "(chunk_id, document_id, chunk_index, body, source_locator) "
                "VALUES (?, ?, ?, ?, ?)",
                (chunk_id, document_id, index, body, locator),
            )
            if has_fts:
                connection.execute(
                    "INSERT INTO knowledge_fts_v2 (chunk_id, title, body) VALUES (?, ?, ?)",
                    (chunk_id, _fts_text(source["title"]), _fts_text(body))
                )
        connection.commit()

    result = {
        "status": "indexed",
        "document_id": document_id,
        "source_id": source["source_id"],
        "file_sha256": digest,
        "chunk_count": len(indexed_chunks),
        "license_status": source["license_status"],
        "language": source["language"],
    }
    if pages_extracted is not None:
        result["pages_extracted"] = pages_extracted
    return result



def seed_core_knowledge() -> dict:
    """Index GEOLOGIA-authored bilingual core checklists; never fetch external sources."""
    if os.environ.get("GEOLOGIA_DISABLE_CORE_SEED") == "1":
        return {
            "seeded_count": 0,
            "already_present_count": 0,
            "source_count": len(CORE_SEEDS),
            "external_downloads": 0,
            "model_used": False,
            "disabled": True,
        }
    initialize()
    with closing(_connect()) as connection:
        existing = {
            row["source_id"]
            for row in connection.execute(
                "SELECT source_id FROM knowledge_documents"
            ).fetchall()
        }

    seeded = []
    already_present = []
    for filename, source_id, title, language in CORE_SEEDS:
        if source_id in existing:
            already_present.append(source_id)
            continue
        source_path = CORE_SEED_DIR / filename
        source_url = (
            "https://github.com/tibatechapp-ship-it/geologia/blob/main/"
            f"src/geologia/data/knowledge_seed/{filename}"
        )
        result = ingest_document(
            source_path,
            {
                "source_id": source_id,
                "title": title,
                "author": "GEOLOGIA Core Knowledge Team",
                "publisher": "GEOLOGIA",
                "source_url": source_url,
                "license_name": "GEOLOGIA original content; repository AGPL-3.0",
                "license_status": "original_work",
                "reviewed_by": "GEOLOGIA core knowledge editorial",
                "review_date": "2026-11-21",
                "language": language,
            },
        )
        if result["status"] == "indexed":
            seeded.append(source_id)
        else:
            already_present.append(source_id)
        existing.add(source_id)
    return {
        "seeded_count": len(seeded),
        "already_present_count": len(already_present),
        "source_count": len(CORE_SEEDS),
        "source_ids": [source_id for _, source_id, _, _ in CORE_SEEDS],
        "external_downloads": 0,
        "model_used": False,
        "disabled": False,
    }


def _tokenize_search_text(text: str) -> list[str]:
    tokens = []
    for token in re.findall(r"[\w]+", text, flags=re.UNICODE):
        if token == "_":
            continue
        tokens.append(token.casefold())
        if CJK_PATTERN.search(token):
            tokens.extend(_cjk_bigrams(token))
    return list(dict.fromkeys(tokens))


def _query_tokens(query: str) -> list[str]:
    return _tokenize_search_text(query)[:MAX_QUERY_TOKENS]


def _matched_query_terms(body: str, title: str, tokens: list[str]) -> list[str]:
    document_terms = set(_tokenize_search_text(body))
    document_terms.update(_tokenize_search_text(title))
    return [token for token in tokens if token.casefold() in document_terms]


def _excerpt(body: str, tokens: list[str], max_chars: int = 900) -> str:
    if len(body) <= max_chars:
        return body
    lowered = body.casefold()
    positions = [lowered.find(token.casefold()) for token in tokens]
    positions = [position for position in positions if position >= 0]
    start = max(0, (min(positions) if positions else 0) - max_chars // 4)
    end = min(len(body), start + max_chars)
    excerpt = body[start:end].strip()
    if start:
        excerpt = "… " + excerpt
    if end < len(body):
        excerpt += " …"
    return excerpt


def search(query: str, limit: int = 5) -> dict:
    """Retrieve indexed text chunks and their reviewed source metadata."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must contain searchable text")
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError("query exceeds the 500 character limit")
    if not isinstance(limit, int) or not 1 <= limit <= 20:
        raise ValueError("limit must be between 1 and 20")
    tokens = _query_tokens(query)
    if not tokens:
        raise ValueError("query must contain letters or numbers")
    initialize()
    seed_core_knowledge()

    rows = []
    with closing(_connect()) as connection:
        has_fts = _fts_available(connection)
        if has_fts:
            match = " OR ".join(f'"{token}"' for token in tokens)
            try:
                rows = connection.execute(
                    """
                    SELECT c.chunk_id, c.document_id, c.chunk_index, c.body, c.source_locator,
                           d.source_id, d.title, d.author, d.publisher, d.source_url,
                           d.doi, d.license_name, d.license_status, d.reviewed_by,
                           d.review_date, d.language, d.file_sha256,
                           bm25(knowledge_fts_v2) AS relevance
                    FROM knowledge_fts_v2
                    JOIN knowledge_chunks c ON c.chunk_id = knowledge_fts_v2.chunk_id
                    JOIN knowledge_documents d ON d.id = c.document_id
                    WHERE knowledge_fts_v2 MATCH ?
                    ORDER BY relevance
                    LIMIT ?
                    """,
                    (match, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        backend = "sqlite_fts5" if has_fts else "sqlite_token_scan"
        if not rows:
            backend = "sqlite_token_scan"
            conditions = []
            filter_parameters = []
            score_terms = []
            score_parameters = []
            for token in tokens:
                conditions.append(
                    "(instr(lower(c.body), lower(?)) > 0 OR "
                    "instr(lower(d.title), lower(?)) > 0)"
                )
                filter_parameters.extend([token, token])
                score_terms.append(
                    "(CASE WHEN instr(lower(c.body), lower(?)) > 0 THEN 1 ELSE 0 END "
                    "+ CASE WHEN instr(lower(d.title), lower(?)) > 0 THEN 1 ELSE 0 END)"
                )
                score_parameters.extend([token, token])
            rows = connection.execute(
                f"""
                SELECT c.chunk_id, c.document_id, c.chunk_index, c.body, c.source_locator,
                       d.source_id, d.title, d.author, d.publisher, d.source_url,
                       d.doi, d.license_name, d.license_status, d.reviewed_by,
                       d.review_date, d.language, d.file_sha256,
                       {" + ".join(score_terms)} AS relevance_score
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.id = c.document_id
                WHERE {" OR ".join(conditions)}
                ORDER BY relevance_score DESC, d.title, c.chunk_index
                LIMIT ?
                """,
                (*score_parameters, *filter_parameters, min(limit * 5, 100)),
            ).fetchall()

    ranked_rows = []
    for row in rows:
        matched_terms = _matched_query_terms(row["body"], row["title"], tokens)
        if not matched_terms:
            continue
        ranked_rows.append((row, matched_terms))
    if backend == "sqlite_token_scan":
        ranked_rows.sort(
            key=lambda item: (
                -len(item[1]),
                item[0]["title"].casefold(),
                item[0]["chunk_index"],
            )
        )
    ranked_rows = ranked_rows[:limit]

    results = []
    for row, matched_terms in ranked_rows:
        citation_url = row["source_url"] or (
            f"https://doi.org/{row['doi']}" if row["doi"] else None
        )
        results.append({
            "chunk_id": row["chunk_id"],
            "source_id": row["source_id"],
            "title": row["title"],
            "author": row["author"],
            "publisher": row["publisher"],
            "source_url": citation_url,
            "doi": row["doi"],
            "license_name": row["license_name"],
            "license_status": row["license_status"],
            "reviewed_by": row["reviewed_by"],
            "review_date": row["review_date"],
            "language": row["language"],
            "file_sha256": row["file_sha256"],
            "chunk_number": row["chunk_index"] + 1,
            "citation_locator": row["source_locator"] or (
                f"local indexed text chunk {row['chunk_index'] + 1}"
            ),
            "matched_query_terms": matched_terms,
            "query_term_coverage": round(len(matched_terms) / len(tokens), 4),
            "retrieval_evidence": "exact_lexical_tokens",
            "excerpt": _excerpt(row["body"], tokens),
        })
    matched_terms = [
        token for token in tokens
        if any(token in result["matched_query_terms"] for result in results)
    ]
    evidence_summary = {
        "query_token_count": len(tokens),
        "matched_query_terms": matched_terms,
        "maximum_query_term_coverage": max(
            (result["query_term_coverage"] for result in results),
            default=0.0,
        ),
        "coverage_scope": "returned_results",
        "coverage_interpretation": (
            "lexical_match_only_not_scientific_confidence"
        ),
        "citable_result_count": sum(
            1 for result in results if result["source_url"]
        ),
    }
    return {
        "query": query.strip(),
        "count": len(results),
        "retrieval_method": backend,
        "model_used": False,
        "scientific_conclusion": False,
        "evidence_summary": evidence_summary,
        "results": results,
    }


def status() -> dict:
    """Return counts and active local search backend without exposing file paths."""
    initialize()
    seed_result = seed_core_knowledge()
    with closing(_connect()) as connection:
        documents = connection.execute(
            "SELECT count(*) FROM knowledge_documents"
        ).fetchone()[0]
        chunks = connection.execute(
            "SELECT count(*) FROM knowledge_chunks"
        ).fetchone()[0]
        backend = "sqlite_fts5" if _fts_available(connection) else "sqlite_token_scan"
    return {
        "storage": "local_sqlite",
        "document_count": documents,
        "chunk_count": chunks,
        "retrieval_method": backend,
        "model_required": False,
        "network_required": False,
        "automatic_downloads_enabled": False,
        "license_review_required_for_ingestion": True,
        "core_seed_count": len(CORE_SEEDS),
        "core_seeded_count": (
            len(seed_result.get("source_ids", []))
            if not seed_result.get("disabled")
            else 0
        ),
        "core_seeded_automatically": os.environ.get("GEOLOGIA_DISABLE_CORE_SEED") != "1",
    }
