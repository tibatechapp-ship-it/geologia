#!/usr/bin/env python3
"""Verify and deterministically sample the published GeographicLib geoid test artifact.

This utility does not calculate geoid heights or perform vertical transformations.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
from typing import Iterable

PUBLISHED_SHA256 = "e0b9804694b3eac78ffd0b3df9cffd30a134d72007276e732ff72f9651bc9995"
EXPECTED_ROWS = 500_000
MODEL_COLUMNS = {"EGM84": 2, "EGM96": 3, "EGM2008": 4}
DEFAULT_SAMPLE_ROWS = (0, 1, 1000, 10000, 100000, 250000, 499999)


class ReferenceArtifactError(ValueError):
    """Raised when a reference artifact fails integrity or structure checks."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _numeric_rows(stream: Iterable[str]):
    for line_number, line in enumerate(stream, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        if len(fields) != 5:
            raise ReferenceArtifactError(
                f"line {line_number}: expected 5 whitespace-separated numeric columns, got {len(fields)}"
            )
        try:
            values = tuple(float(field) for field in fields)
        except ValueError as exc:
            raise ReferenceArtifactError(f"line {line_number}: non-numeric value") from exc
        if not all(math.isfinite(value) for value in values):
            raise ReferenceArtifactError(f"line {line_number}: non-finite value")
        latitude, longitude = values[:2]
        if not -90.0 <= latitude <= 90.0:
            raise ReferenceArtifactError(f"line {line_number}: latitude outside [-90, 90]")
        if not -180.0 <= longitude <= 360.0:
            raise ReferenceArtifactError(f"line {line_number}: longitude outside accepted source range")
        yield values


def verify_and_extract(
    artifact: Path,
    *,
    expected_sha256: str = PUBLISHED_SHA256,
    expected_rows: int = EXPECTED_ROWS,
    sample_rows: tuple[int, ...] = DEFAULT_SAMPLE_ROWS,
    model: str = "EGM2008",
) -> dict:
    """Verify compressed bytes, parse all rows, and return stable reference samples."""
    if model not in MODEL_COLUMNS:
        raise ReferenceArtifactError(f"unsupported model column: {model}")
    if any(index < 0 or index >= expected_rows for index in sample_rows):
        raise ReferenceArtifactError("sample row index outside expected dataset")
    actual_sha256 = sha256_file(artifact)
    if actual_sha256.lower() != expected_sha256.lower():
        raise ReferenceArtifactError(
            f"SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )

    samples = {}
    row_count = 0
    try:
        with gzip.open(artifact, "rt", encoding="ascii", newline="") as stream:
            for values in _numeric_rows(stream):
                if row_count in sample_rows:
                    samples[str(row_count)] = {
                        "latitude_degrees": values[0],
                        "longitude_degrees": values[1],
                        "geoid_height_m": values[MODEL_COLUMNS[model]],
                    }
                row_count += 1
    except (OSError, EOFError, UnicodeError) as exc:
        raise ReferenceArtifactError(f"invalid gzip/text artifact: {exc}") from exc

    if row_count != expected_rows:
        raise ReferenceArtifactError(
            f"row count mismatch: expected {expected_rows}, got {row_count}"
        )
    missing = sorted(set(sample_rows) - {int(key) for key in samples})
    if missing:
        raise ReferenceArtifactError(f"sample rows missing from artifact: {missing}")

    return {
        "schema_version": 1,
        "dataset_id": "geographiclib-geoid-heights-500k",
        "artifact_filename": artifact.name,
        "artifact_sha256": actual_sha256,
        "verified_row_count": row_count,
        "model_column": model,
        "selection_basis": "zero-based data-row indices; comments and blank lines excluded",
        "samples": samples,
        "scientific_scope": (
            "Published model regression reference; not field-survey truth and not a vertical "
            "transformation validation."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path, help="Downloaded GeoidHeights.dat.gz")
    parser.add_argument("--output", type=Path, required=True, help="JSON sample manifest path")
    parser.add_argument("--model", choices=tuple(MODEL_COLUMNS), default="EGM2008")
    args = parser.parse_args()
    result = verify_and_extract(args.artifact, model=args.model)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {result['verified_row_count']} rows; SHA-256 {result['artifact_sha256']}")
    print(f"Wrote deterministic {args.model} samples to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
