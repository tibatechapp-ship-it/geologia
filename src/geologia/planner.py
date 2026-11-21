"""Deterministic, plan-only routing. This module never executes engines."""
INTENTS = [
    {"domain": "hydrology", "engines": ["modflow6", "pastas"],
     "inputs": ["well_logs", "water_levels_timeseries", "recharge_estimate", "dem", "geology_map"],
     "keywords": ["مياه", "جوفية", "بئر", "groundwater", "aquifer", "well", "pumping"]},
    {"domain": "geology3d", "engines": ["gempy", "loopstructural", "map2loop"],
     "inputs": ["geology_map", "structural_orientations", "contacts", "dem"],
     "keywords": ["ثلاثي", "طيات", "فوالق", "3d", "cross-section", "geological model"]},
    {"domain": "seismology", "engines": ["obspy", "openquake"],
     "inputs": ["waveforms_or_catalog", "station_metadata"],
     "keywords": ["زلزال", "زلازل", "seismic", "earthquake", "waveform"]},
    {"domain": "exploration", "engines": ["eis-toolkit", "geopytool"],
     "inputs": ["geochemistry_samples", "geophysics_surveys", "geology_map"],
     "keywords": ["ذهب", "معدن", "تنقيب", "gold", "mineral", "exploration"]},
    {"domain": "remote_sensing", "engines": ["opendronemap"],
     "inputs": ["imagery", "ground_control_points"],
     "keywords": ["درون", "استشعار", "قمر صناعي", "drone", "satellite"]},
    {"domain": "gis", "engines": ["geopandas", "rasterio", "qgis"],
     "inputs": ["aoi_boundary", "data_layers", "crs_definition"],
     "keywords": ["خريطة", "طبقات", "gis", "map", "layers"]},
]
GATES = [
    "data_sufficiency", "crs_and_units", "engine_execution_evidence",
    "warnings_review", "reproducibility", "uncertainty", "independent_review",
]


def build_plan(request: str, language: str = "ar") -> dict:
    text = request.casefold()
    matched = [item for item in INTENTS if any(word in text for word in item["keywords"])]
    if not matched:
        matched = [next(item for item in INTENTS if item["domain"] == "gis")]
    steps, required = [], set()
    for item in matched:
        steps.append({
            "domain": item["domain"], "candidate_engines": item["engines"],
            "required_inputs": item["inputs"], "engine_status": "planned",
            "execution": "not_started",
        })
        required.update(item["inputs"])
    disclaimer = (
        "هذه خطة فقط؛ لم تُنفّذ محركات ولم تُحسب نتائج علمية. "
        "لا توصية بالحفر أو تأكيد مورد دون بيانات كافية ومراجعة علمية."
        if language == "ar" else
        "Plan only: no engines ran and no scientific results were computed. "
        "No drilling or resource confirmation without sufficient data and scientific review."
    )
    return {
        "plan_only": True, "no_results_computed": True, "language": language,
        "matched_domains": [step["domain"] for step in steps], "steps": steps,
        "required_inputs": sorted(required), "scientific_gates": GATES,
        "disclaimer": disclaimer,
    }
