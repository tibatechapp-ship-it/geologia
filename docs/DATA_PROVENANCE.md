# Dataset provenance event chain

GEOLOGIA records a local append-only event sequence for dataset ingestion, structural inspection, and schema validation.

## Event envelope

Each event contains:
- unique event ID, project ID, dataset ID, event type, and UTC timestamp;
- canonical JSON payload with sorted keys and compact separators;
- the previous event hash within the project;
- SHA-256 of the canonical envelope.

Dataset ingestion records the original filename, format, byte size, upload-time SHA-256, declared CRS, data role, and available derivation metadata. Inspection and validation events bind their reports to the dataset ID and source digest.

## Verification

`GET /api/v1/datasets/{dataset_id}/provenance` returns the selected dataset's events and verifies the entire project event chain in sequence. A changed payload, event hash, or previous-hash link yields `chain_integrity: failed`.

This is **tamper-evident, not tamper-proof**. A user with direct write access to the SQLite database can rewrite and recompute the entire chain. Production-grade immutability requires a separate restricted audit store or externally anchored digest, which is not implemented.

## Scope

The event chain is local SQLite audit metadata. It does not prove that the source is authoritative, that a license is valid, that the declared CRS/datum is correct, or that a scientific result is accurate. It preserves provenance facts and detects accidental or partial database tampering; it is not scientific validation.
