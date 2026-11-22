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
MAX_GPKG_FIELDS = 4096
MAX_METADATA_ITEMS = 128
MAX_METADATA_VALUE_LENGTH = 2048
MAX_LAS_VLRS = 10_000
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


def _parsed_crs(crs: Any) -> Any:
    if crs is None:
        return None
    try:
        from pyproj import CRS
        return CRS.from_user_input(crs)
    except (ImportError, TypeError, ValueError):
        return None


def _crs_axis_units(crs: Any) -> list[str]:
    parsed = _parsed_crs(crs)
    return [axis.unit_name for axis in parsed.axis_info] if parsed is not None else []


def _vertical_reference(
    crs: Any, tags: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Report declared vertical CRS/tags without asserting datum verification."""
    parsed = _parsed_crs(crs)
    if crs is None:
        parse_status = "no_crs_declared"
    elif parsed is None:
        parse_status = "crs_parse_failed"
    else:
        parse_status = "parsed"
    components = []
    if parsed is not None:
        try:
            candidates = list(parsed.sub_crs_list) if parsed.is_compound else [parsed]
            for component in candidates:
                if not component.is_vertical:
                    continue
                authority = component.to_authority()
                datum = component.datum
                components.append({
                    "crs": component.to_string(),
                    "authority": authority[0] if authority else None,
                    "code": authority[1] if authority else None,
                    "name": component.name,
                    "datum_name": datum.name if datum is not None else None,
                    "axis_units": [axis.unit_name for axis in component.axis_info],
                    "axis_directions": [axis.direction for axis in component.axis_info],
                })
        except (AttributeError, TypeError, ValueError):
            components = []

    vertical_values = {}
    for key, value in (tags or {}).items():
        lowered = str(key).lower()
        if any(token in lowered for token in ("vertical", "geoid", "datum", "height")):
            vertical_values[str(key)[:256]] = str(value)[:MAX_METADATA_VALUE_LENGTH]

    return {
        "vertical_crs_parse_status": (
            "vertical_component_found" if components else
            "no_vertical_component_in_crs" if parse_status == "parsed" else parse_status
        ),
        "declared_vertical_crs": [item["crs"] for item in components] or None,
        "vertical_crs_components": components,
        "vertical_metadata_keys": sorted(vertical_values),
        "vertical_metadata_values": vertical_values,
        "vertical_datum_verified": False,
        "vertical_transformation_performed": False,
    }

def inspect_geopackage(path: Path) -> dict[str, Any]:
    """Check SQLite/GPKG structure and inspect bounded layer metadata."""
    size = _check_file(Path(path))
    with Path(path).open("rb") as source:
        signature = source.read(16)
    if signature != b"SQLite format 3\x00":
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

    pyogrio = _dependency("pyogrio")
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
            fields = list(info.get("fields", []))
            if len(fields) > MAX_GPKG_FIELDS:
                raise FormatValidationError("GeoPackage layer contains too many fields")
            crs = info.get("crs")
            layers.append({
                "name": name,
                "geometry_type": info.get("geometry_type"),
                "feature_count": info.get("features"),
                "fields": fields,
                "crs": crs,
                "coordinate_units": _crs_axis_units(crs),
                "srs_id": next((row[2] for row in contents if row[0] == name), None),
                "vertical_reference": _vertical_reference(crs),
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
        "validation": "container_layer_metadata_and_feature_sample",
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
            metadata = {
                str(key)[:256]: str(value)[:MAX_METADATA_VALUE_LENGTH]
                for key, value in list(tags.items())[:MAX_METADATA_ITEMS]
            }
            metadata_truncated = (
                len(tags) > MAX_METADATA_ITEMS
                or any(len(str(value)) > MAX_METADATA_VALUE_LENGTH for value in tags.values())
            )
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
                "coordinate_units": _crs_axis_units(crs),
                "transform": [float(value) for value in dataset.transform],
                "bounds": bounds,
                "band_dtypes": list(dataset.dtypes),
                "band_units": units,
                "nodata_values": [
                    float(value) if value is not None and math.isfinite(float(value)) else None
                    for value in dataset.nodatavals
                ],
                "block_shapes": [list(shape) for shape in block_shapes],
                "compression": [str(dataset.compression.value) if dataset.compression else None],
                "metadata": metadata,
                "metadata_truncated": metadata_truncated,
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
            if not all(
                math.isfinite(float(value)) and float(value) != 0
                for value in header.scales
            ) or not all(math.isfinite(float(value)) for value in header.offsets):
                raise FormatValidationError(
                    "LAS scale/offset values must be finite and scales non-zero"
                )
            expected_end = point_offset + count * record_length
            if expected_end > size:
                raise FormatValidationError("LAS point records extend beyond end of file")
            if count and count > 50_000_000:
                raise FormatValidationError("LAS point count exceeds inspection limit")
            sampled = 0
            for points in reader.chunk_iterator(min(LAS_SAMPLE_POINTS, max(count, 1))):
                axes = (points.x, points.y, points.z)
                if not all(
                    math.isfinite(float(value))
                    for axis in axes
                    for value in axis
                ):
                    raise FormatValidationError("LAS sample contains non-finite coordinates")
                sampled = len(points)
                break
            crs = header.parse_crs()
            evlrs = list(header.evlrs or [])
            if len(header.vlrs) + len(evlrs) > MAX_LAS_VLRS:
                raise FormatValidationError("LAS contains too many variable-length records")
            vlrs = [{
                "user_id": str(vlr.user_id),
                "record_id": int(vlr.record_id),
                "description": str(vlr.description),
            } for vlr in header.vlrs]
            extended_vlrs = [{
                "user_id": str(vlr.user_id),
                "record_id": int(vlr.record_id),
                "description": str(vlr.description),
            } for vlr in evlrs]
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
                "coordinate_units": _crs_axis_units(crs),
                "vlr_count": len(vlrs),
                "vlrs": vlrs,
                "evlr_count": len(extended_vlrs),
                "evlrs": extended_vlrs,
                "vertical_reference": _vertical_reference(crs),
                "scientific_validation": False,
            }
            return report
    except FormatValidationError:
        raise
    except Exception as exc:
        raise FormatValidationError("LAS file is corrupt, truncated, or unsupported") from exc


def _polygonal_aoi(payload: dict[str, Any]):
    _dependency("shapely")
    from shapely.geometry import shape
    from shapely.ops import unary_union

    kind = payload.get("type")
    if kind == "FeatureCollection":
        features = payload.get("features")
        if not isinstance(features, list):
            raise FormatValidationError("AOI FeatureCollection.features must be an array")
        geometries = [
            feature.get("geometry")
            for feature in features
            if isinstance(feature, dict)
            and feature.get("type") == "Feature"
            and feature.get("geometry") is not None
        ]
    elif kind == "Feature":
        geometries = [payload.get("geometry")]
    elif kind in {"Polygon", "MultiPolygon"}:
        geometries = [payload]
    else:
        raise FormatValidationError("AOI must be a Polygon or MultiPolygon GeoJSON")

    try:
        parsed = [shape(geometry) for geometry in geometries if isinstance(geometry, dict)]
        if not parsed:
            raise FormatValidationError("AOI contains no polygon geometry")
        aoi = unary_union(parsed)
    except FormatValidationError:
        raise
    except Exception as exc:
        raise FormatValidationError("AOI polygon geometry cannot be decoded") from exc
    if aoi.geom_type not in {"Polygon", "MultiPolygon"} or aoi.is_empty:
        raise FormatValidationError("AOI must resolve to a non-empty Polygon or MultiPolygon")
    if not aoi.is_valid or aoi.area <= 0:
        raise FormatValidationError("AOI polygon must be valid and have positive area")
    if len(aoi.wkb) > 16 * 1024 * 1024:
        raise FormatValidationError("AOI geometry exceeds the supported complexity limit")
    return aoi


def _densify_geometry_for_crs(geometry: Any, crs: Any):
    """Densify polygon edges before CRS transformation to limit chord error."""
    if crs.is_geographic:
        max_segment_length = 0.01  # approximately 1.1 km north-south
    else:
        axes = crs.axis_info
        factors = [
            float(axis.unit_conversion_factor or 0)
            for axis in axes[:2]
        ]
        if len(factors) < 2 or any(
            not math.isfinite(factor) or factor <= 0
            for factor in factors
        ):
            raise FormatValidationError(
                "CRS axis units cannot be converted for boundary densification"
            )
        max_segment_length = 1000.0 / min(factors)

    polygons = list(geometry.geoms) if geometry.geom_type == "MultiPolygon" else [geometry]
    estimated_segments = 0
    for polygon in polygons:
        rings = [polygon.exterior, *polygon.interiors]
        for ring in rings:
            coordinates = list(ring.coords)
            for first, second in zip(coordinates, coordinates[1:]):
                length = math.hypot(
                    second[0] - first[0],
                    second[1] - first[1],
                )
                estimated_segments += max(1, math.ceil(length / max_segment_length))
                if estimated_segments > 1_000_000:
                    raise FormatValidationError(
                        "AOI boundary exceeds the CRS densification complexity limit"
                    )
    try:
        return geometry.segmentize(max_segment_length)
    except AttributeError as exc:
        raise FormatValidationError(
            "AOI CRS transformation requires Shapely with geometry segmentize support"
        ) from exc


def inspect_dem_aoi_coverage(
    dem_path: Path,
    aoi_payload: dict[str, Any],
    aoi_crs: str,
) -> dict[str, Any]:
    """Measure a DEM raster extent and valid-data mask against one declared AOI.

    This is a coverage inspection, not an accuracy test. It reads raster masks
    block-by-block, not elevation values, and reports pixel-center area estimates
    separately from the exact polygon extent intersection.
    """
    size = _check_file(Path(dem_path))
    rasterio = _dependency("rasterio")
    numpy = _dependency("numpy")
    pyproj = _dependency("pyproj")
    from rasterio.features import geometry_mask
    from shapely.geometry import Polygon, mapping
    from shapely.ops import transform as transform_geometry

    try:
        aoi = _polygonal_aoi(aoi_payload)
        aoi_source_crs = pyproj.CRS.from_user_input(aoi_crs)
        if (
            aoi_source_crs.is_compound
            or aoi_source_crs.is_vertical
            or not (aoi_source_crs.is_geographic or aoi_source_crs.is_projected)
        ):
            raise FormatValidationError("AOI CRS must be a horizontal 2D CRS")
        if (
            aoi_source_crs.is_geographic
            and aoi.bounds[2] - aoi.bounds[0] > 180
        ):
            raise FormatValidationError(
                "AOI crosses the antimeridian; split it into non-crossing polygons"
            )
        area_crs = pyproj.CRS.from_epsg(6933)
        to_area = pyproj.Transformer.from_crs(
            aoi_source_crs, area_crs, always_xy=True
        )
        aoi_area_geometry = transform_geometry(
            to_area.transform,
            _densify_geometry_for_crs(aoi, aoi_source_crs),
        )
        aoi_area_m2 = float(aoi_area_geometry.area)
        if not math.isfinite(aoi_area_m2) or aoi_area_m2 <= 0:
            raise FormatValidationError("AOI area cannot be measured in the equal-area CRS")

        with rasterio.open(Path(dem_path), "r") as dataset:
            width, height, bands = dataset.width, dataset.height, dataset.count
            if width <= 0 or height <= 0 or bands <= 0:
                raise FormatValidationError("DEM dimensions and band count must be positive")
            if width * height > MAX_RASTER_PIXELS or bands > MAX_RASTER_BANDS:
                raise FormatValidationError("DEM dimensions exceed inspection limits")
            if dataset.crs is None:
                raise FormatValidationError("DEM must declare a horizontal CRS")
            raster_crs = pyproj.CRS.from_user_input(dataset.crs)
            if not raster_crs.is_projected or raster_crs.is_compound:
                raise FormatValidationError(
                    "DEM must use a projected horizontal CRS for area-based coverage inspection"
                )
            axes = raster_crs.axis_info
            if len(axes) < 2:
                raise FormatValidationError("DEM projected CRS must declare two horizontal axes")
            factor_x = float(axes[0].unit_conversion_factor or 0)
            factor_y = float(axes[1].unit_conversion_factor or 0)
            if (
                not math.isfinite(factor_x)
                or not math.isfinite(factor_y)
                or factor_x <= 0
                or factor_y <= 0
            ):
                raise FormatValidationError("DEM CRS axis units cannot be converted to metres")

            transform = dataset.transform
            affine_values = [
                float(transform.a), float(transform.b), float(transform.c),
                float(transform.d), float(transform.e), float(transform.f),
            ]
            if not all(math.isfinite(value) for value in affine_values):
                raise FormatValidationError("DEM affine transform must be finite")
            determinant = abs(transform.a * transform.e - transform.b * transform.d)
            pixel_area_grid_m2 = determinant * factor_x * factor_y
            if not math.isfinite(pixel_area_grid_m2) or pixel_area_grid_m2 <= 0:
                raise FormatValidationError("DEM pixel area must be positive and finite")

            block_shapes = [tuple(shape) for shape in dataset.block_shapes]
            if any(
                block_height * block_width * numpy.dtype(dataset.dtypes[index]).itemsize
                > MAX_RASTER_BLOCK_BYTES
                for index, (block_height, block_width) in enumerate(block_shapes)
            ):
                raise FormatValidationError("DEM block size exceeds the memory safety limit")

            to_raster = pyproj.Transformer.from_crs(
                aoi_source_crs, raster_crs, always_xy=True
            )
            aoi_in_raster = transform_geometry(
                to_raster.transform,
                _densify_geometry_for_crs(aoi, aoi_source_crs),
            )
            if aoi_in_raster.is_empty or not aoi_in_raster.is_valid:
                raise FormatValidationError("AOI cannot be transformed to the DEM CRS")

            corners = [
                transform * (0, 0),
                transform * (width, 0),
                transform * (width, height),
                transform * (0, height),
            ]
            raster_footprint = Polygon(corners)
            if raster_footprint.is_empty or not raster_footprint.is_valid:
                raise FormatValidationError("DEM affine transform does not form a valid footprint")
            intersection = aoi_in_raster.intersection(raster_footprint)
            to_area_from_raster = pyproj.Transformer.from_crs(
                raster_crs, area_crs, always_xy=True
            )
            if intersection.is_empty:
                intersection_area_m2 = 0.0
                representative_point = raster_footprint.representative_point()
            else:
                intersection_for_area = _densify_geometry_for_crs(
                    intersection, raster_crs, pyproj
                )
                intersection_area_m2 = float(
                    transform_geometry(
                        to_area_from_raster.transform, intersection_for_area
                    ).area
                )
                representative_point = intersection.representative_point()

            column, row = (~transform) * (
                representative_point.x, representative_point.y
            )
            column = min(max(math.floor(column), 0), width - 1)
            row = min(max(math.floor(row), 0), height - 1)
            pixel_polygon = Polygon([
                transform * (column, row),
                transform * (column + 1, row),
                transform * (column + 1, row + 1),
                transform * (column, row + 1),
            ])
            pixel_area_m2 = float(
                transform_geometry(to_area_from_raster.transform, pixel_polygon).area
            )
            if not math.isfinite(pixel_area_m2) or pixel_area_m2 <= 0:
                raise FormatValidationError(
                    "DEM pixel area cannot be measured in the equal-area CRS"
                )

            aoi_pixel_count_in_raster = 0
            valid_aoi_pixel_count = 0
            if not intersection.is_empty and intersection_area_m2 > 0:
                aoi_mapping = mapping(aoi_in_raster)
                for _, window in dataset.block_windows(1):
                    window_height = int(window.height)
                    window_width = int(window.width)
                    inside = geometry_mask(
                        [aoi_mapping],
                        out_shape=(window_height, window_width),
                        transform=dataset.window_transform(window),
                        invert=True,
                        all_touched=False,
                    )
                    inside_count = int(numpy.count_nonzero(inside))
                    if inside_count == 0:
                        continue
                    valid_mask = dataset.read_masks(1, window=window) > 0
                    aoi_pixel_count_in_raster += inside_count
                    valid_aoi_pixel_count += int(numpy.count_nonzero(inside & valid_mask))

            valid_pixel_area_estimate_m2 = valid_aoi_pixel_count * pixel_area_m2
            extent_fraction = intersection_area_m2 / aoi_area_m2
            valid_area_fraction = valid_pixel_area_estimate_m2 / aoi_area_m2
            valid_fraction_within_extent = (
                valid_aoi_pixel_count / aoi_pixel_count_in_raster
                if aoi_pixel_count_in_raster
                else 0.0
            )
            aoi_fully_within_raster_extent = bool(
                raster_footprint.covers(aoi_in_raster)
            )
            all_aoi_pixel_centres_valid = bool(
                aoi_pixel_count_in_raster > 0
                and valid_aoi_pixel_count == aoi_pixel_count_in_raster
            )
            if intersection_area_m2 == 0:
                coverage_status = "no_extent_overlap"
            elif valid_aoi_pixel_count == 0:
                coverage_status = "overlap_without_valid_pixels"
            elif aoi_fully_within_raster_extent and all_aoi_pixel_centres_valid:
                coverage_status = "full_aoi_extent_and_valid_pixels"
            elif valid_aoi_pixel_count < aoi_pixel_count_in_raster:
                coverage_status = "partial_valid_data_within_raster_extent"
            else:
                coverage_status = "partial_aoi_extent_with_valid_pixels"

            return {
                "format": "dem_aoi_coverage_inspection",
                "inspection_status": "measured",
                "coverage_status": coverage_status,
                "aoi_fully_within_raster_extent": aoi_fully_within_raster_extent,
                "all_aoi_pixel_centres_valid": all_aoi_pixel_centres_valid,
                "file_size_bytes": size,
                "raster_width": width,
                "raster_height": height,
                "raster_band_count": bands,
                "raster_crs": raster_crs.to_string(),
                "aoi_crs": aoi_source_crs.to_string(),
                "raster_extent_bounds": [
                    float(value) for value in dataset.bounds
                ],
                "aoi_area_m2": aoi_area_m2,
                "raster_extent_intersection_area_m2": intersection_area_m2,
                "raster_extent_intersection_fraction_of_aoi": extent_fraction,
                "aoi_pixel_centres_inside_raster": aoi_pixel_count_in_raster,
                "valid_aoi_pixel_centres": valid_aoi_pixel_count,
                "valid_pixel_fraction_within_raster_extent": valid_fraction_within_extent,
                "pixel_area_m2": pixel_area_m2,
                "pixel_area_estimation_method": (
                    "representative pixel transformed to EPSG:6933; local estimate"
                ),
                "crs_boundary_densification": (
                    "AOI edges densified to approximately 1 km before CRS transformations"
                ),
                "valid_pixel_area_estimate_m2": valid_pixel_area_estimate_m2,
                "valid_pixel_coverage_fraction_estimate": valid_area_fraction,
                "resolution_x_m": math.hypot(transform.a, transform.d) * factor_x,
                "resolution_y_m": math.hypot(transform.b, transform.e) * factor_y,
                "mask_band": 1,
                "mask_method": "rasterio read_masks; block-wise",
                "aoi_pixel_selection": "pixel centre (all_touched=False)",
                "area_estimation_limit": (
                    "valid pixel area is a pixel-count estimate; AOI boundary pixels "
                    "are not fractionally clipped, so the estimate can differ by "
                    "approximately one pixel along the boundary"
                ),
                "vertical_datum_verified": False,
                "dem_accuracy_validated": False,
                "scientific_interpretation": False,
            }
    except FormatValidationError:
        raise
    except Exception as exc:
        raise FormatValidationError(
            "DEM/AOI coverage inspection failed because an input is invalid or unsupported"
        ) from exc
