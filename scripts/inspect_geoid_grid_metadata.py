#!/usr/bin/env python3
"""Read-only structural inspection of pinned geoid GeoTIFF metadata.

A passing result confirms only the expected raster dimensions, CRS, and a
non-rotated global geographic grid layout. It is not a license/tide-system
decision, an interpolation comparison, or permission for vertical conversion.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "src" / "geologia" / "data" / "geoid_grid_integrity.json"


def inspect_grid(path: Path, spec: dict[str, Any]) -> dict[str, Any]:
    """Inspect one GeoTIFF without modifying it or reading raster values."""
    result: dict[str, Any] = {
        "model_id": spec["model_id"],
        "file_name": spec["file_name"],
        "status": "metadata_unverified",
        "checks": {},
    }
    if not path.is_file():
        result["status"] = "rejected"
        result["reason"] = "grid file is unavailable"
        return result

    try:
        import rasterio
        from rasterio.crs import CRS
    except ImportError:
        result["status"] = "metadata_unverified"
        result["reason"] = "rasterio is required; install the optional formats extra"
        return result

    try:
        with rasterio.open(path, "r") as dataset:
            actual_crs = dataset.crs
            expected_crs = CRS.from_string(spec["horizontal_crs"])
            transform = dataset.transform
            bounds = dataset.bounds
            checks = {
                "dimensions_match": (
                    dataset.width == spec["width"] and dataset.height == spec["height"]
                ),
                "single_band": dataset.count == 1,
                "horizontal_crs_matches": actual_crs == expected_crs,
                "north_up_unrotated": (
                    math.isfinite(transform.a)
                    and math.isfinite(transform.e)
                    and math.isfinite(transform.b)
                    and math.isfinite(transform.d)
                    and transform.a > 0
                    and transform.e < 0
                    and abs(transform.b) <= 1e-12
                    and abs(transform.d) <= 1e-12
                ),
                "global_geographic_extent": (
                    actual_crs == CRS.from_epsg(4326)
                    and bounds.left <= -179.0
                    and bounds.right >= 179.0
                    and bounds.bottom <= -89.0
                    and bounds.top >= 89.0
                ),
            }
            result.update(
                {
                    "actual_width": dataset.width,
                    "actual_height": dataset.height,
                    "actual_band_count": dataset.count,
                    "actual_crs": actual_crs.to_string() if actual_crs else None,
                    "transform": [float(value) for value in transform[:6]],
                    "bounds": {
                        "left": float(bounds.left),
                        "bottom": float(bounds.bottom),
                        "right": float(bounds.right),
                        "top": float(bounds.top),
                    },
                    "pixel_size_degrees": [float(transform.a), float(transform.e)],
                    "checks": checks,
                }
            )
    except Exception as exc:  # parser errors are reported as unverified, not trusted
        result["status"] = "rejected"
        result["reason"] = f"GeoTIFF metadata could not be read: {type(exc).__name__}"
        return result

    if all(checks.values()):
        result["status"] = "metadata_matches_pinned_expectations"
        result["reason"] = (
            "basic raster metadata matches; scientific datum, licensing, "
            "interpolation and vertical transformation remain unverified"
        )
    else:
        result["status"] = "rejected"
        result["reason"] = "one or more structural metadata checks failed"
    return result


def inspect_directory(directory: Path, manifest: dict | None = None) -> dict:
    if manifest is None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest.get("schema") != "geologia-geoid-grid-integrity/1":
        raise ValueError("unsupported geoid integrity manifest schema")
    grids = manifest.get("grids")
    if not isinstance(grids, list) or not grids:
        raise ValueError("manifest must contain a non-empty grids list")
    results = [inspect_grid(directory / item["file_name"], item) for item in grids]
    passed = all(item["status"] == "metadata_matches_pinned_expectations" for item in results)
    return {
        "schema": "geologia-geoid-metadata-report/1",
        "operation": "read_only_geoid_metadata_inspection",
        "metadata_checks_passed": passed,
        "scientific_validation": False,
        "vertical_transformation_enabled": False,
        "results": results,
        "limitations": [
            "Metadata inspection does not verify the pinned file SHA-256; run the byte-integrity verifier separately.",
            "No raster values were read and no interpolation was performed.",
            "No independent PROJ cross-check was performed.",
            "License, tide system, input height datum and vertical transformation remain unverified.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=ROOT / "download" / "geoid_grids",
        help="directory containing the locally supplied geoid GeoTIFF files",
    )
    args = parser.parse_args()
    report = inspect_directory(args.directory)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["metadata_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
