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

    if geometry.geom_type == "Polygon":
        polygons = [geometry]
    elif geometry.geom_type == "MultiPolygon":
        polygons = list(geometry.geoms)
    elif geometry.geom_type == "GeometryCollection":
        polygons = [
            item for item in geometry.geoms
            if item.geom_type in {"Polygon", "MultiPolygon"}
        ]
        if not polygons:
            return geometry
    else:
        return geometry
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
                    intersection, raster_crs
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


MAX_DEM_COVERAGE_TILE_BYTES = 2 * 1024 * 1024 * 1024
MAX_DEM_COVERAGE_TILES = 256
MAX_DEM_COVERAGE_TOTAL_BYTES = 50 * 1024 * 1024 * 1024
MAX_DEM_MOSAIC_PIXELS = 1_000_000_000
DEM_COVERAGE_WINDOW_SIZE = 512


def inspect_dem_tile_collection_coverage(
    dem_paths: list[Path],
    aoi_payload: dict[str, Any],
    aoi_crs: str,
) -> dict[str, Any]:
    """Inspect a same-grid DEM tile collection against an AOI, window by window.

    Tile footprints are unioned so overlap is not double-counted and gaps remain
    visible. Valid pixel centres are counted once on the common mosaic grid.
    This is coverage inspection, not DEM accuracy validation.
    """
    import hashlib
    from contextlib import ExitStack

    rasterio = _dependency("rasterio")
    numpy = _dependency("numpy")
    pyproj = _dependency("pyproj")
    from affine import Affine
    from rasterio.features import geometry_mask
    from rasterio.windows import Window
    from shapely.geometry import Polygon, mapping
    from shapely.ops import transform as transform_geometry, unary_union

    if not dem_paths or len(dem_paths) > MAX_DEM_COVERAGE_TILES:
        raise FormatValidationError(
            f"DEM tile collection must contain 1 to {MAX_DEM_COVERAGE_TILES} files"
        )
    paths = [Path(item) for item in dem_paths]
    if len({path.resolve() for path in paths}) != len(paths):
        raise FormatValidationError("DEM tile collection contains duplicate paths")

    def sha256_file(path: Path) -> tuple[int, str]:
        digest = hashlib.sha256()
        total = 0
        try:
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    total += len(chunk)
                    if total > MAX_DEM_COVERAGE_TILE_BYTES:
                        raise FormatValidationError(
                            "DEM tile exceeds the 2 GiB coverage-inspection limit"
                        )
                    digest.update(chunk)
        except OSError as exc:
            raise FormatValidationError("DEM tile cannot be read") from exc
        if total == 0:
            raise FormatValidationError("DEM tile must be non-empty")
        return total, digest.hexdigest()

    try:
        aoi = _polygonal_aoi(aoi_payload)
        source_crs = pyproj.CRS.from_user_input(aoi_crs)
        if (
            source_crs.is_compound
            or source_crs.is_vertical
            or not (source_crs.is_geographic or source_crs.is_projected)
        ):
            raise FormatValidationError("AOI CRS must be a horizontal 2D CRS")
        if source_crs.is_geographic and aoi.bounds[2] - aoi.bounds[0] > 180:
            raise FormatValidationError(
                "AOI crosses the antimeridian; split it into non-crossing polygons"
            )

        with ExitStack() as stack:
            tiles: list[dict[str, Any]] = []
            total_file_size_bytes = 0
            reference_transform = None
            reference_crs = None
            for path in paths:
                size_bytes, digest = sha256_file(path)
                total_file_size_bytes += size_bytes
                if total_file_size_bytes > MAX_DEM_COVERAGE_TOTAL_BYTES:
                    raise FormatValidationError(
                        "DEM tile collection exceeds the 50 GiB total file-size limit"
                    )
                try:
                    dataset = stack.enter_context(rasterio.open(path, "r"))
                except Exception as exc:
                    raise FormatValidationError("DEM tile cannot be opened") from exc
                if dataset.width <= 0 or dataset.height <= 0 or dataset.count < 1:
                    raise FormatValidationError("DEM tile dimensions and bands must be positive")
                if dataset.width * dataset.height > MAX_RASTER_PIXELS:
                    raise FormatValidationError("DEM tile exceeds the per-file pixel limit")
                if dataset.crs is None:
                    raise FormatValidationError("DEM tile must declare a horizontal CRS")
                tile_crs = pyproj.CRS.from_user_input(dataset.crs)
                if not (tile_crs.is_projected or tile_crs.is_geographic):
                    raise FormatValidationError(
                        "DEM tiles must use a common horizontal projected or geographic CRS"
                    )
                transform = dataset.transform
                affine_values = (
                    transform.a, transform.b, transform.c,
                    transform.d, transform.e, transform.f,
                )
                if not all(math.isfinite(float(value)) for value in affine_values):
                    raise FormatValidationError("DEM tile affine transform must be finite")
                determinant = transform.a * transform.e - transform.b * transform.d
                if not math.isfinite(determinant) or abs(determinant) <= 0:
                    raise FormatValidationError("DEM tile affine transform is singular")
                for index, (block_height, block_width) in enumerate(dataset.block_shapes):
                    block_bytes = (
                        block_height * block_width
                        * numpy.dtype(dataset.dtypes[index]).itemsize
                    )
                    if block_bytes > MAX_RASTER_BLOCK_BYTES:
                        raise FormatValidationError(
                            "DEM tile block size exceeds the memory safety limit"
                        )

                if reference_transform is None:
                    reference_transform = transform
                    reference_crs = tile_crs
                else:
                    if not tile_crs.equals(reference_crs):
                        raise FormatValidationError(
                            "DEM tiles must share one CRS; reproject tiles before inspection"
                        )
                    if any(
                        not math.isclose(left, right, rel_tol=0, abs_tol=1e-9)
                        for left, right in zip(
                            (transform.a, transform.b, transform.d, transform.e),
                            (
                                reference_transform.a, reference_transform.b,
                                reference_transform.d, reference_transform.e,
                            ),
                        )
                    ):
                        raise FormatValidationError(
                            "DEM tiles must share identical pixel-grid orientation "
                            "and resolution"
                        )
                offset_col, offset_row = (~reference_transform) * (
                    transform.c, transform.f
                )
                rounded_col, rounded_row = round(offset_col), round(offset_row)
                if (
                    not math.isclose(offset_col, rounded_col, abs_tol=1e-6)
                    or not math.isclose(offset_row, rounded_row, abs_tol=1e-6)
                ):
                    raise FormatValidationError(
                        "DEM tile origins are not aligned to the common pixel grid"
                    )
                footprint = Polygon([
                    transform * (0, 0),
                    transform * (dataset.width, 0),
                    transform * (dataset.width, dataset.height),
                    transform * (0, dataset.height),
                ])
                if footprint.is_empty or not footprint.is_valid:
                    raise FormatValidationError("DEM tile footprint is invalid")
                tiles.append({
                    "path": path.name,
                    "size_bytes": size_bytes,
                    "sha256": digest,
                    "dataset": dataset,
                    "transform": transform,
                    "width": dataset.width,
                    "height": dataset.height,
                    "offset_col": int(rounded_col),
                    "offset_row": int(rounded_row),
                    "footprint": footprint,
                })

            min_col = min(tile["offset_col"] for tile in tiles)
            min_row = min(tile["offset_row"] for tile in tiles)
            max_col = max(
                tile["offset_col"] + tile["width"] for tile in tiles
            )
            max_row = max(
                tile["offset_row"] + tile["height"] for tile in tiles
            )
            mosaic_width, mosaic_height = max_col - min_col, max_row - min_row
            if mosaic_width <= 0 or mosaic_height <= 0:
                raise FormatValidationError("DEM tile mosaic dimensions are invalid")
            if mosaic_width * mosaic_height > MAX_DEM_MOSAIC_PIXELS:
                raise FormatValidationError("DEM tile mosaic exceeds the processing pixel limit")
            for tile in tiles:
                tile["mosaic_col"] = tile["offset_col"] - min_col
                tile["mosaic_row"] = tile["offset_row"] - min_row
            mosaic_transform = reference_transform * Affine.translation(min_col, min_row)

            aoi_in_mosaic = transform_geometry(
                pyproj.Transformer.from_crs(
                    source_crs, reference_crs, always_xy=True
                ).transform,
                _densify_geometry_for_crs(aoi, source_crs),
            )
            if aoi_in_mosaic.is_empty or not aoi_in_mosaic.is_valid:
                raise FormatValidationError("AOI cannot be transformed to the common DEM grid")

            tile_union = unary_union([tile["footprint"] for tile in tiles])
            intersection = aoi_in_mosaic.intersection(tile_union)
            area_crs = pyproj.CRS.from_epsg(6933)
            to_area = pyproj.Transformer.from_crs(
                reference_crs, area_crs, always_xy=True
            )
            aoi_area = float(
                transform_geometry(
                    pyproj.Transformer.from_crs(
                        source_crs, area_crs, always_xy=True
                    ).transform,
                    _densify_geometry_for_crs(aoi, source_crs),
                ).area
            )
            if not math.isfinite(aoi_area) or aoi_area <= 0:
                raise FormatValidationError(
                    "AOI area cannot be measured in the equal-area CRS"
                )
            union_area = float(
                transform_geometry(
                    to_area.transform,
                    _densify_geometry_for_crs(tile_union, reference_crs),
                ).area
            )
            intersection_area = (
                float(
                    transform_geometry(
                        to_area.transform,
                        _densify_geometry_for_crs(intersection, reference_crs),
                    ).area
                )
                if not intersection.is_empty
                else 0.0
            )
            gap_geometry = aoi_in_mosaic.difference(tile_union)
            gap_area = (
                float(
                    transform_geometry(
                        to_area.transform,
                        _densify_geometry_for_crs(gap_geometry, reference_crs),
                    ).area
                )
                if not gap_geometry.is_empty
                else 0.0
            )
            sum_tile_area = sum(
                float(
                    transform_geometry(
                        to_area.transform,
                        _densify_geometry_for_crs(tile["footprint"], reference_crs),
                    ).area
                )
                for tile in tiles
            )
            overlap_area = max(0.0, sum_tile_area - union_area)
            full_extent = bool(tile_union.covers(aoi_in_mosaic))

            inside_count = 0
            valid_count = 0
            aoi_mapping = mapping(aoi_in_mosaic)
            for row in range(0, mosaic_height, DEM_COVERAGE_WINDOW_SIZE):
                window_height = min(DEM_COVERAGE_WINDOW_SIZE, mosaic_height - row)
                for col in range(0, mosaic_width, DEM_COVERAGE_WINDOW_SIZE):
                    window_width = min(DEM_COVERAGE_WINDOW_SIZE, mosaic_width - col)
                    inside = geometry_mask(
                        [aoi_mapping],
                        out_shape=(window_height, window_width),
                        transform=mosaic_transform * Affine.translation(col, row),
                        invert=True,
                        all_touched=False,
                    )
                    count_inside = int(numpy.count_nonzero(inside))
                    if count_inside == 0:
                        continue
                    valid = numpy.zeros((window_height, window_width), dtype=bool)
                    for tile in tiles:
                        tile_col, tile_row = tile["mosaic_col"], tile["mosaic_row"]
                        overlap_col = max(col, tile_col)
                        overlap_row = max(row, tile_row)
                        overlap_col_end = min(col + window_width, tile_col + tile["width"])
                        overlap_row_end = min(row + window_height, tile_row + tile["height"])
                        if overlap_col >= overlap_col_end or overlap_row >= overlap_row_end:
                            continue
                        overlap_width = overlap_col_end - overlap_col
                        overlap_height = overlap_row_end - overlap_row
                        source_window = Window(
                            overlap_col - tile_col,
                            overlap_row - tile_row,
                            overlap_width,
                            overlap_height,
                        )
                        source_mask = tile["dataset"].read_masks(1, window=source_window) > 0
                        target_rows = slice(overlap_row - row, overlap_row_end - row)
                        target_cols = slice(overlap_col - col, overlap_col_end - col)
                        valid[target_rows, target_cols] |= source_mask
                    inside_count += count_inside
                    valid_count += int(numpy.count_nonzero(inside & valid))

            pixel_polygon = Polygon([
                mosaic_transform * (0, 0),
                mosaic_transform * (1, 0),
                mosaic_transform * (1, 1),
                mosaic_transform * (0, 1),
            ])
            pixel_area = float(
                transform_geometry(to_area.transform, pixel_polygon).area
            )
            if not math.isfinite(pixel_area) or pixel_area <= 0:
                raise FormatValidationError("mosaic pixel area must be positive and finite")
            valid_pixel_area_estimate = valid_count * pixel_area
            extent_fraction = (
                min(1.0, max(0.0, intersection_area / aoi_area))
                if aoi_area > 0
                else 0.0
            )
            valid_area_fraction = (
                valid_pixel_area_estimate / aoi_area if aoi_area > 0 else None
            )
            all_centres_valid = inside_count > 0 and valid_count == inside_count
            if intersection_area <= 0:
                status = "no_extent_overlap"
            elif valid_count == 0:
                status = "overlap_without_valid_pixels"
            elif full_extent and all_centres_valid:
                status = "full_aoi_extent_and_valid_pixels"
            elif valid_count < inside_count:
                status = "partial_valid_data_within_raster_extent"
            else:
                status = "partial_aoi_extent_with_valid_pixels"

            return {
                "format": "dem_tile_collection_coverage_inspection",
                "inspection_status": "measured",
                "coverage_status": status,
                "aoi_fully_within_raster_extent": full_extent,
                "all_aoi_pixel_centres_valid": all_centres_valid,
                "tile_count": len(tiles),
                "total_file_size_bytes": total_file_size_bytes,
                "tiles": [
                    {
                        "filename": tile["path"],
                        "file_size_bytes": tile["size_bytes"],
                        "sha256": tile["sha256"],
                        "width": tile["width"],
                        "height": tile["height"],
                        "mosaic_column_offset": tile["mosaic_col"],
                        "mosaic_row_offset": tile["mosaic_row"],
                        "affine_transform": [
                            float(tile["transform"].a), float(tile["transform"].b),
                            float(tile["transform"].c), float(tile["transform"].d),
                            float(tile["transform"].e), float(tile["transform"].f),
                        ],
                    }
                    for tile in tiles
                ],
                "mosaic_width": mosaic_width,
                "mosaic_height": mosaic_height,
                "mosaic_crs": reference_crs.to_string(),
                "mosaic_transform": [
                    float(mosaic_transform.a), float(mosaic_transform.b),
                    float(mosaic_transform.c), float(mosaic_transform.d),
                    float(mosaic_transform.e), float(mosaic_transform.f),
                ],
                "aoi_area_m2": aoi_area,
                "raster_extent_intersection_area_m2": intersection_area,
                "raster_extent_intersection_fraction_of_aoi": extent_fraction,
                "uncovered_aoi_area_m2": gap_area,
                "overlap_area_m2": overlap_area,
                "aoi_pixel_centres_in_mosaic": inside_count,
                "valid_aoi_pixel_centres": valid_count,
                "valid_pixel_fraction_within_mosaic": (
                    valid_count / inside_count if inside_count else 0.0
                ),
                "valid_pixel_area_estimate_m2": valid_pixel_area_estimate,
                "valid_pixel_coverage_fraction_estimate": valid_area_fraction,
                "pixel_area_m2": pixel_area,
                "pixel_area_estimation_method": (
                    "one mosaic-grid pixel transformed to EPSG:6933; local estimate"
                ),
                "mask_method": "windowed union of rasterio read_masks across aligned tiles",
                "aoi_pixel_selection": "pixel centre; overlaps counted once on common grid",
                "vertical_datum_verified": False,
                "dem_accuracy_validated": False,
                "scientific_interpretation": False,
            }
    except FormatValidationError:
        raise
    except Exception as exc:
        raise FormatValidationError(
            "DEM tile collection coverage inspection failed because an input "
            "is invalid or unsupported"
        ) from exc
