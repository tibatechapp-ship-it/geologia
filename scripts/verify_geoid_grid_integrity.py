#!/usr/bin/env python3
"""Verify byte identity of locally supplied geoid grids against pinned hashes.

This is a read-only integrity check. It does not parse GeoTIFF tags, validate
license/tide-system claims, cross-check interpolation, or authorize vertical
transformations. A matching hash proves only that the bytes match this pin.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "geologia" / "data" / "geoid_grid_integrity.json"
CHUNK_SIZE = 1024 * 1024


def load_manifest(path: Path = MANIFEST) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "geologia-geoid-grid-integrity/1":
        raise ValueError("unsupported geoid integrity manifest schema")
    grids = data.get("grids")
    if not isinstance(grids, list) or not grids:
        raise ValueError("manifest must contain a non-empty grids list")
    names = set()
    for grid in grids:
        name = grid.get("file_name")
        digest = grid.get("sha256")
        size = grid.get("expected_size_bytes")
        if not isinstance(name, str) or Path(name).name != name or name in names:
            raise ValueError("grid file names must be unique simple filenames")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"invalid SHA-256 pin for {name!r}")
        try:
            int(digest, 16)
        except ValueError as exc:
            raise ValueError(f"invalid SHA-256 pin for {name!r}") from exc
        if not isinstance(size, int) or size <= 0:
            raise ValueError(f"invalid expected file size for {name!r}")
        names.add(name)
    return data


def verify_file(path: Path, spec: dict) -> dict:
    expected_size = spec["expected_size_bytes"]
    expected_hash = spec["sha256"].lower()
    result = {
        "model_id": spec["model_id"],
        "file_name": spec["file_name"],
        "status": "integrity_unverified",
        "expected_size_bytes": expected_size,
        "expected_sha256": expected_hash,
    }
    try:
        actual_size = path.stat().st_size
    except OSError as exc:
        result["reason"] = f"file unavailable: {exc}"
        return result
    result["actual_size_bytes"] = actual_size
    if actual_size != expected_size:
        result["status"] = "rejected"
        result["reason"] = "file size does not match pinned reference"
        return result
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
                digest.update(chunk)
    except OSError as exc:
        result["reason"] = f"file read failed: {exc}"
        return result
    actual_hash = digest.hexdigest()
    result["actual_sha256"] = actual_hash
    if actual_hash != expected_hash:
        result["status"] = "rejected"
        result["reason"] = "SHA-256 does not match pinned reference"
        return result
    result["status"] = "byte_integrity_verified"
    result["reason"] = "bytes match the pinned manifest; scientific and licensing gates remain unverified"
    return result


def verify_directory(directory: Path, manifest: dict | None = None) -> dict:
    manifest = manifest or load_manifest()
    results = [
        verify_file(directory / spec["file_name"], spec)
        for spec in manifest["grids"]
    ]
    return {
        "schema": "geologia-geoid-integrity-report/1",
        "operation": "read_only_geoid_byte_integrity",
        "scientific_validation": False,
        "vertical_transformation_enabled": False,
        "results": results,
        "overall_status": (
            "byte_integrity_verified"
            if all(item["status"] == "byte_integrity_verified" for item in results)
            else "integrity_not_verified"
        ),
        "limitations": [
            "No GeoTIFF parsing or geospatial metadata validation was performed.",
            "No license or tide-system claim was independently verified.",
            "No PROJ interpolation cross-check was performed.",
            "This report does not authorize geoid undulation or elevation answers.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=ROOT / "download" / "geoid_grids",
        help="directory containing the locally downloaded pinned grid files",
    )
    args = parser.parse_args()
    report = verify_directory(args.directory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["overall_status"] == "byte_integrity_verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
