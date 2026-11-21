# Remote sensing and imagery — product readiness

Original GEOLOGIA checklist. An image file is not automatically a calibrated scientific product.

## Required metadata
- Sensor/platform, acquisition date/time, processing level, product identifier, and data provider.
- Band names/wavelengths, pixel size, radiometric scale/offset, units, and whether values are DN, radiance, top-of-atmosphere reflectance, or surface reflectance.
- CRS, geolocation quality, scene footprint, cloud/shadow QA, atmospheric correction, and any resampling.
- Ground-control points (GCPs), control source, residuals, and independent check points for photogrammetric products.

## Preflight
1. Read product metadata and QA bands before selecting indices or classification methods.
2. Do not combine scenes with incompatible sensors, bands, seasons, or processing levels without a documented harmonization method.
3. Mask clouds, shadows, saturation, and invalid pixels using the product's QA scheme.
4. Preserve original imagery and record every derived operation.
5. Check whether the image or ancillary layer includes third-party licensing restrictions.

## Interpretation boundary
Remote sensing can support mapping and change detection, but a spectral signature alone does not prove mineralization, groundwater, or a geological unit. Ground truth and independent validation are needed.

## References
- NASA Landsat data overview: https://science.nasa.gov/mission/landsat/data-overview/
- USGS Landsat public-domain and citation guidance: https://www.usgs.gov/faqs/are-landsat-data-cloud-still-considered-be-within-public-domain
