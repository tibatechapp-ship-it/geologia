"""Small, local, license-reviewed text retrieval index for GEOLOGIA.

Uses Python's SQLite and optionally its built-in FTS5 extension. No embeddings,
model weights, remote APIs, automatic downloads, or source-code execution.
"""
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlparse
from uuid import uuid4

MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_CHUNK_CHARS = 1600
CHUNK_OVERLAP_CHARS = 180
MAX_QUERY_CHARS = 500
MAX_QUERY_TOKENS = 12
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json"}
LICENSE_STATUSES = {
    "public_domain", "open_license", "permission", "original_work"
}

CORE_SEEDS = [
    ("hydrology_en.md", "geologia-core-hydrology-en-v1", "Groundwater data readiness", "en"),
    ("hydrology_ar.md", "geologia-core-hydrology-ar-v1", "جاهزية بيانات المياه الجوفية", "ar"),
    ("gis_crs_en.md", "geologia-core-gis-crs-en-v1", "GIS and CRS preflight", "en"),
    ("gis_crs_ar.md", "geologia-core-gis-crs-ar-v1", "فحص نظم المعلومات الجغرافية والإحداثيات", "ar"),
    ("geology3d_en.md", "geologia-core-geology3d-en-v1", "3D geological modeling evidence", "en"),
    ("geology3d_ar.md", "geologia-core-geology3d-ar-v1", "أدلة النمذجة الجيولوجية ثلاثية الأبعاد", "ar"),
    ("seismology_en.md", "geologia-core-seismology-en-v1", "Seismology data quality", "en"),
    ("seismology_ar.md", "geologia-core-seismology-ar-v1", "جودة بيانات الزلازل", "ar"),
    ("remote_sensing_en.md", "geologia-core-remote-sensing-en-v1", "Remote sensing product readiness", "en"),
    ("remote_sensing_ar.md", "geologia-core-remote-sensing-ar-v1", "جاهزية منتجات الاستشعار عن بعد", "ar"),
    ("mineral_exploration_en.md", "geologia-core-mineral-exploration-en-v1", "Mineral exploration QA/QC", "en"),
    ("mineral_exploration_ar.md", "geologia-core-mineral-exploration-ar-v1", "ضبط جودة استكشاف المعادن", "ar"),
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


def _fts_available(connection: sqlite3.Connection) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'knowledge_fts'"
    ).fetchone() is not None


def initialize() -> None:
    """Create the local knowledge schema; FTS5 is optional with a safe fallback."""
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
                UNIQUE(document_id, chunk_index)
            );

            CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_document
                ON knowledge_chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_knowledge_documents_doi
                ON knowledge_documents(doi);
            """
        )
        try:
            connection.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts "
                "USING fts5(chunk_id UNINDEXED, title, body, tokenize='unicode61')"
            )
        except sqlite3.OperationalError:
            # Some mobile/system SQLite builds omit FTS5. The local token-scan
            # fallback remains functional and does not add a runtime dependency.
            pass
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


def ingest_document(path: str | Path, metadata: dict) -> dict:
    """Index a locally supplied text document after explicit license review."""
    source_path = Path(path).expanduser()
    if source_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError("only UTF-8 .txt, .md, .csv, and .json files can be indexed")
    if not source_path.is_file():
        raise ValueError("source file does not exist or is not a regular file")

    raw = source_path.read_bytes()
    if not raw:
        raise ValueError("source file is empty")
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError("source file exceeds the 20 MiB local indexing limit")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("source text must be UTF-8") from exc
    if "\x00" in text:
        raise ValueError("source text contains NUL bytes")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("source text contains no indexable content")

    source = _validate_metadata(metadata)
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("source text produced no searchable chunks")
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
        for index, body in enumerate(chunks):
            chunk_id = uuid4().hex
            connection.execute(
                "INSERT INTO knowledge_chunks (chunk_id, document_id, chunk_index, body) "
                "VALUES (?, ?, ?, ?)",
                (chunk_id, document_id, index, body),
            )
            if has_fts:
                connection.execute(
                    "INSERT INTO knowledge_fts (chunk_id, title, body) VALUES (?, ?, ?)",
                    (chunk_id, source["title"], body),
                )
        connection.commit()

    return {
        "status": "indexed",
        "document_id": document_id,
        "source_id": source["source_id"],
        "file_sha256": digest,
        "chunk_count": len(chunks),
        "license_status": source["license_status"],
        "language": source["language"],
    }



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


def _query_tokens(query: str) -> list[str]:
    tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)
    return [token for token in tokens if token != "_"][:MAX_QUERY_TOKENS]


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
                    SELECT c.chunk_id, c.document_id, c.chunk_index, c.body,
                           d.source_id, d.title, d.author, d.publisher, d.source_url,
                           d.doi, d.license_name, d.license_status, d.reviewed_by,
                           d.review_date, d.language, d.file_sha256,
                           bm25(knowledge_fts) AS relevance
                    FROM knowledge_fts
                    JOIN knowledge_chunks c ON c.chunk_id = knowledge_fts.chunk_id
                    JOIN knowledge_documents d ON d.id = c.document_id
                    WHERE knowledge_fts MATCH ?
                    ORDER BY relevance
                    LIMIT ?
                    """,
                    (match, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = []
        backend = "sqlite_fts5" if has_fts else "sqlite_token_scan"
        if not rows and not has_fts:
            conditions = []
            parameters = []
            for token in tokens:
                conditions.append(
                    "(instr(lower(c.body), lower(?)) > 0 OR "
                    "instr(lower(d.title), lower(?)) > 0)"
                )
                parameters.extend([token, token])
            rows = connection.execute(
                f"""
                SELECT c.chunk_id, c.document_id, c.chunk_index, c.body,
                       d.source_id, d.title, d.author, d.publisher, d.source_url,
                       d.doi, d.license_name, d.license_status, d.reviewed_by,
                       d.review_date, d.language, d.file_sha256
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.id = c.document_id
                WHERE {" OR ".join(conditions)}
                ORDER BY d.title, c.chunk_index
                LIMIT ?
                """,
                (*parameters, limit),
            ).fetchall()

    results = []
    for row in rows:
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
            "citation_locator": (
                f"local indexed text chunk {row['chunk_index'] + 1}; "
                "original page/section locator is not inferred"
            ),
            "excerpt": _excerpt(row["body"], tokens),
        })
    return {
        "query": query.strip(),
        "count": len(results),
        "retrieval_method": backend,
        "model_used": False,
        "scientific_conclusion": False,
        "results": results,
    }


def status() -> dict:
    """Return counts and active local search backend without exposing file paths."""
    initialize()
    seed_core_knowledge()
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
        "core_seeded_automatically": os.environ.get("GEOLOGIA_DISABLE_CORE_SEED") != "1",
    }
