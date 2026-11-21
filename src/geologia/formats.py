"""Bounded structural inspection of GeoPackage, GeoTIFF, and uncompressed LAS files.

These routines inspect file integrity and declared metadata only. They do not
interpret geological meaning or certify measurements.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Any

MAX_FORMAT_FILE_BYTES = 50 * 1024 * 1024
MAX_RASTER_PIXELS = 100_000_000
MAX_RASTER_BANDS = 256
MAX_RASTER_BLOCK_BYTES = 64 * 1024 * 1024
MAX_GPKG_LAYERS = 128
LAS_SAMPLE_POINTS = 100_000


class FormatValidationError(ValueError):
    """The file is malformed, incompatible, or exceeds inspection limits."""


class FormatDependencyError(RuntimeError):
    """The optional parser dependency for a format is not installed."""


def _check_file(path: Path) -> int:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise FormatValidationError("dataset file cannot be accessed") from exc
    if not path.is_file() or size <= 0:
        raise FormatValidationError("dataset must be a non-empty regular file")
    if size > MAX_FORMAT_FILE_BYTES:
        raise FormatValidationError("dataset exceeds the format-inspection size limit")
    return size


def _dependency(name: str):
    try:
        return __import__(name)
    except ImportError as exc:
        raise FormatDependencyError(
            f"format inspection requires the optional 'formats' extra ({name})"
        ) from exc


def _vertical_reference(crs: Any, tags: dict[str, Any] | None = None) -> dict[str, Any]:
    vertical_crs = None
    if crs is not None:
        try:
            sub_crs = crs.sub_crs_list
            vertical = [item for item in sub_crs if item.is_vertical]
            if vertical:
                vertical_crs = [item.to_string() for item in vertical]
            elif getattr(crs, "is_vertical", False):
                vertical_crs = [crs.to_string()]
        except (AttributeError, TypeError, ValueError):
            vertical_crs = None
    tag_names = []
    for key in (tags or {}):
        lowered = str(key).lower()
        if any(token in lowered for token in ("vertical", "geoid", "datum", "height")):
            tag_names.append(str(key))
    return {
        "declared_vertical_crs": vertical_crs,
        "vertical_metadata_keys": sorted(tag_names),
        "vertical_datum_verified": False,
        "vertical_transformation_performed": False,
    }


def inspect_geopackage(path: Path) -> dict[str, Any]:
    """Check SQLite/GPKG structure and inspect bounded layer metadata."""
    size = _check_file(Path(path))
    pyogrio = _dependency("pyogrio")
    if Path(path).read_bytes()[:16] != b"SQLite format 3\x00":
        raise FormatValidationError("GeoPackage must be a SQLite database")
    try:
        connection = sqlite3.connect(f"file:{Path(path).resolve()}?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        check = connection.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise FormatValidationError("GeoPackage SQLite integrity check failed")
        tables = {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if not {"gpkg_contents", "gpkg_spatial_ref_sys"}.issubset(tables):
            raise FormatValidationError("required GeoPackage metadata tables are missing")
        contents = connection.execute(
            "SELECT table_name, data_type, srs_id FROM gpkg_contents ORDER BY table_name"
        ).fetchall()
        if len(contents) > MAX_GPKG_LAYERS:
            raise FormatValidationError("GeoPackage contains too many registered layers")
    except sqlite3.DatabaseError as exc:
        raise FormatValidationError("GeoPackage database is corrupt or unreadable") from exc
    finally:
        if "connection" in locals():
            connection.close()

    try:
        raw_layers = pyogrio.list_layers(Path(path))
        if len(raw_layers) > MAX_GPKG_LAYERS:
            raise FormatValidationError("GeoPackage contains too many layers")
        layers = []
        for entry in raw_layers:
            name = str(entry[0])
            try:
                info = pyogrio.read_info(Path(path), layer=name)
            except Exception as exc:
                raise FormatValidationError("GeoPackage layer metadata cannot be read") from exc
            crs = info.get("crs")
            layers.append({
                "name": name,
                "geometry_type": info.get("geometry_type"),
                "feature_count": info.get("features"),
                "fields": list(info.get("fields", [])),
                "crs": crs,
                "srs_id": next((row[2] for row in contents if row[0] == name), None),
                "vertical_reference": _vertical_reference(None),
            })
            try:
                sample = pyogrio.read_dataframe(Path(path), layer=name, max_features=1000)
            except Exception as exc:
                raise FormatValidationError("GeoPackage feature sample cannot be decoded") from exc
            layers[-1]["sample_feature_count"] = len(sample)
    except FormatValidationError:
        raise
    except Exception as exc:
        raise FormatValidationError("GeoPackage layers cannot be inspected") from exc
    return {
        "format": "gpkg",
        "validation": "container_and_layer_metadata",
        "file_size_bytes": size,
        "sqlite_integrity": "passed",
        "layer_count": len(layers),
        "layers": layers,
        "scientific_validation": False,
        "vertical_datum_verified": False,
    }


def inspect_geotiff(path: Path) -> dict[str, Any]:
    """Inspect TIFF raster header and read only a bounded sample window."""
    size = _check_file(Path(path))
    rasterio = _dependency("rasterio")
    numpy = _dependency("numpy")
    try:
        with rasterio.open(Path(path), "r") as dataset:
            width, height, bands = dataset.width, dataset.height, dataset.count
            if width <= 0 or height <= 0 or bands <= 0:
                raise FormatValidationError("GeoTIFF dimensions and band count must be positive")
            if width * height > MAX_RASTER_PIXELS or bands > MAX_RASTER_BANDS:
                raise FormatValidationError("GeoTIFF dimensions exceed inspection limits")
            block_shapes = [tuple(shape) for shape in dataset.block_shapes]
            if any(
                block_height * block_width * numpy.dtype(dataset.dtypes[index]).itemsize
                > MAX_RASTER_BLOCK_BYTES
                for index, (block_height, block_width) in enumerate(block_shapes)
            ):
                raise FormatValidationError("GeoTIFF block size exceeds the memory safety limit")
            sample_width = min(width, 32)
            sample_height = min(height, 32)
            dataset.read(1, window=((0, sample_height), (0, sample_width)))
            tags = dataset.tags()
            crs = dataset.crs
            bounds = [float(value) for value in dataset.bounds]
            if not all(math.isfinite(value) for value in bounds):
                raise FormatValidationError("GeoTIFF bounds must be finite")
            units = list(dataset.units) if dataset.units else []
            report = {
                "format": "geotiff",
                "validation": "raster_header_and_sample",
                "file_size_bytes": size,
                "width": width,
                "height": height,
                "band_count": bands,
                "pixel_count": width * height,
                "crs": crs.to_string() if crs else None,
                "transform": [float(value) for value in dataset.transform],
                "bounds": bounds,
                "band_dtypes": list(dataset.dtypes),
                "band_units": units,
                "nodata_values": list(dataset.nodatavals),
                "block_shapes": [list(shape) for shape in block_shapes],
                "compression": [str(value.value) if value else None
                               for value in dataset.compressions],
                "metadata": {key: str(value) for key, value in tags.items()},
                "vertical_reference": _vertical_reference(crs, tags),
                "sample_window": {"width": sample_width, "height": sample_height},
                "scientific_validation": False,
            }
            return report
    except FormatValidationError:
        raise
    except Exception as exc:
        raise FormatValidationError("GeoTIFF is corrupt, truncated, or unsupported") from exc


def inspect_las(path: Path) -> dict[str, Any]:
    """Validate LAS header/point-data bounds and read a bounded point sample."""
    size = _check_file(Path(path))
    laspy = _dependency("laspy")
    try:
        with laspy.open(Path(path)) as reader:
            header = reader.header
            count = int(header.point_count)
            record_length = int(header.point_format.size)
            point_offset = int(header.offset_to_point_data)
            if count < 0 or record_length <= 0 or point_offset < 0:
                raise FormatValidationError("LAS header contains invalid point-data values")
            expected_end = point_offset + count * record_length
            if expected_end > size:
                raise FormatValidationError("LAS point records extend beyond end of file")
            if count and count > 50_000_000:
                raise FormatValidationError("LAS point count exceeds inspection limit")
            sampled = 0
            for points in reader.chunk_iterator(min(LAS_SAMPLE_POINTS, max(count, 1))):
                xyz = points.xyz
                if not all(math.isfinite(float(value)) for value in xyz.reshape(-1)):
                    raise FormatValidationError("LAS sample contains non-finite coordinates")
                sampled = len(points)
                break
            crs = header.parse_crs()
            vlrs = [{
                "user_id": str(vlr.user_id),
                "record_id": int(vlr.record_id),
                "description": str(vlr.description),
            } for vlr in header.vlrs]
            report = {
                "format": "las",
                "validation": "header_point_bounds_and_sample",
                "file_size_bytes": size,
                "las_version": str(header.version),
                "point_format_id": int(header.point_format.id),
                "point_record_length": record_length,
                "point_count": count,
                "point_data_offset": point_offset,
                "sampled_point_count": sampled,
                "scale": [float(value) for value in header.scales],
                "offset": [float(value) for value in header.offsets],
                "crs": crs.to_string() if crs else None,
                "vlr_count": len(vlrs),
                "vlrs": vlrs,
                "vertical_reference": _vertical_reference(crs),
                "scientific_validation": False,
            }
            return report
    except FormatValidationError:
        raise
    except Exception as exc:
        raise FormatValidationError("LAS file is corrupt, truncated, or unsupported") from exc
