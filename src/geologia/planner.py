"""Model-independent, deterministic request routing for the Ali Algomori agent.

This module creates explainable plans only. It never runs a scientific engine,
downloads a model, calls a remote inference API, or manufactures a GIS fallback
when the request does not identify a geoscience domain.
"""
import re
import unicodedata

INTENTS = [
    {
        "domain": "hydrology",
        "engines": ["modflow6", "pastas"],
        "inputs": [
            "well_logs", "water_levels_timeseries", "recharge_estimate", "dem", "geology_map"
        ],
        "keywords": [
            "مياه", "المياه", "ماء", "الماء", "مياه جوفية", "المياه الجوفية",
            "جوفية", "الجوفية", "بئر", "آبار", "groundwater", "aquifer",
            "well", "pumping", "water table", "hydrogeology",
        ],
    },
    {
        "domain": "geology3d",
        "engines": ["gempy", "loopstructural", "map2loop"],
        "inputs": ["geology_map", "structural_orientations", "contacts", "dem"],
        "keywords": [
            "ثلاثي", "طيات", "الفوالق", "فوالق", "مقطع جيولوجي", "3d",
            "cross section", "geological model", "structural geology",
        ],
    },
    {
        "domain": "seismology",
        "engines": ["obspy", "openquake"],
        "inputs": ["waveforms_or_catalog", "station_metadata"],
        "keywords": [
            "زلزال", "زلازل", "الزلازل", "زلزالي", "seismic", "earthquake",
            "waveform", "ground motion",
        ],
    },
    {
        "domain": "exploration",
        "engines": ["eis-toolkit", "geopytool"],
        "inputs": ["geochemistry_samples", "geophysics_surveys", "geology_map"],
        "keywords": [
            "ذهب", "الذهب", "معدن", "المعادن", "تنقيب", "استكشاف معدني",
            "gold", "mineral", "minerals", "exploration", "prospectivity",
        ],
    },
    {
        "domain": "remote_sensing",
        "engines": ["opendronemap"],
        "inputs": ["imagery", "ground_control_points"],
        "keywords": [
            "درون", "استشعار عن بعد", "القمر الصناعي", "الأقمار الصناعية",
            "قمر صناعي", "صور فضائية", "drone", "satellite", "remote sensing",
            "photogrammetry",
        ],
    },
    {
        "domain": "gis",
        "engines": ["geopandas", "rasterio", "qgis"],
        "inputs": ["aoi_boundary", "data_layers", "crs_definition"],
        "keywords": [
            "خريطة", "الخريطة", "خرائط", "طبقات", "نظم المعلومات الجغرافية",
            "gis", "map", "maps", "layers", "geographic information system",
        ],
    },
]
AGENT_ROLES = {
    "hydrology": ("groundwater_specialist", "وكيل المياه الجوفية", "Groundwater specialist"),
    "geology3d": ("geology3d_specialist", "وكيل النمذجة ثلاثية الأبعاد", "3D geology specialist"),
    "seismology": ("seismology_specialist", "وكيل الزلازل", "Seismology specialist"),
    "exploration": (
        "mineral_exploration_specialist", "وكيل استكشاف المعادن",
        "Mineral exploration specialist",
    ),
    "remote_sensing": (
        "remote_sensing_specialist", "وكيل الاستشعار عن بعد",
        "Remote sensing specialist",
    ),
    "gis": ("gis_specialist", "وكيل نظم المعلومات الجغرافية", "GIS specialist"),
}
GATES = [
    "data_sufficiency", "crs_and_units", "engine_execution_evidence",
    "warnings_review", "reproducibility", "uncertainty", "independent_review",
]
AGENT_ID = "ali-algomori"
AGENT_NAME_AR = "علي الگوموري"
AGENT_NAME_EN = "Ali Algomori"


def agent_status() -> dict:
    """Describe the built-in agent without implying model training or engine execution."""
    return {
        "agent_id": AGENT_ID,
        "name_ar": AGENT_NAME_AR,
        "name_en": AGENT_NAME_EN,
        "architecture": "deterministic_rule_based",
        "runtime": "local",
        "model_required": False,
        "network_required": False,
        "scientific_execution_enabled": False,
        "capabilities": [
            "request_classification",
            "routing_evidence",
            "domain_routing",
            "data_role_readiness",
            "explainable_plan_generation",
        ],
        "limitations": [
            "No neural model is trained or loaded.",
            "No scientific engine is executed.",
            "Routing confidence is heuristic and not calibrated.",
            "A plan is not a scientific result or professional certification.",
        ],
    }


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _contains_phrase(normalized_text: str, keyword: str) -> bool:
    normalized_keyword = _normalize(keyword)
    if not normalized_keyword:
        return False
    return f" {normalized_keyword} " in f" {normalized_text} "


def _confidence_level(evidence_count: int) -> str:
    if evidence_count >= 3:
        return "high"
    if evidence_count == 2:
        return "medium"
    if evidence_count == 1:
        return "low"
    return "none"


def classify_request(request: str) -> dict:
    """Return deterministic domain matches and the keyword evidence for each."""
    if not isinstance(request, str):
        raise ValueError("request must be a string")
    normalized = _normalize(request)
    matches = []
    for intent in INTENTS:
        evidence = [
            keyword for keyword in intent["keywords"]
            if _contains_phrase(normalized, keyword)
        ]
        if evidence:
            matches.append({
                "domain": intent["domain"],
                "evidence": evidence,
                "confidence_level": _confidence_level(len(evidence)),
                "evidence_count": len(evidence),
            })
    if matches:
        return {
            "classification_status": "matched",
            "needs_clarification": False,
            "matched_domains": [item["domain"] for item in matches],
            "routing_evidence": matches,
            "confidence_basis": "distinct keyword evidence; confidence is heuristic, not calibrated",
        }
    return {
        "classification_status": "needs_clarification",
        "needs_clarification": True,
        "matched_domains": [],
        "routing_evidence": [],
        "confidence_basis": "no domain keyword evidence",
    }


def build_plan(request: str, language: str = "ar") -> dict:
    """Build an explainable plan without invoking models or scientific engines."""
    classification = classify_request(request)
    matched_domains = classification["matched_domains"]
    evidence_by_domain = {
        item["domain"]: item for item in classification["routing_evidence"]
    }
    steps, required, assignments = [], set(), []
    for domain in matched_domains:
        item = next(intent for intent in INTENTS if intent["domain"] == domain)
        evidence = evidence_by_domain[domain]
        steps.append({
            "domain": domain,
            "candidate_engines": item["engines"],
            "required_inputs": item["inputs"],
            "engine_status": "planned",
            "execution": "not_started",
            "routing_evidence": evidence["evidence"],
            "confidence_level": evidence["confidence_level"],
        })
        required.update(item["inputs"])
        role = AGENT_ROLES[domain]
        assignments.append({"role_id": role[0], "name_ar": role[1], "name_en": role[2]})

    needs_clarification = classification["needs_clarification"]
    if language == "ar":
        disclaimer = (
            "هذه خطة فقط؛ لم تُنفّذ محركات ولم تُحسب نتائج علمية. "
            "لا توصية بالحفر أو تأكيد مورد دون بيانات كافية ومراجعة علمية."
        )
        clarification = (
            "حدد المجال المطلوب: المياه الجوفية، النمذجة ثلاثية الأبعاد، "
            "الزلازل، استكشاف المعادن، الاستشعار عن بعد، أم نظم المعلومات الجغرافية؟"
        )
    else:
        disclaimer = (
            "Plan only: no engines ran and no scientific results were computed. "
            "No drilling or resource confirmation without sufficient data and scientific review."
        )
        clarification = (
            "Please specify the domain: groundwater, 3D geology, seismology, "
            "mineral exploration, remote sensing, or GIS."
        )

    confidence = (
        max((item["evidence_count"] for item in classification["routing_evidence"]), default=0)
    )
    return {
        "plan_only": True,
        "no_results_computed": True,
        "language": language,
        "chief_agent": {
            "agent_id": AGENT_ID,
            "name_ar": AGENT_NAME_AR,
            "name_en": AGENT_NAME_EN,
        },
        "agent_runtime": {
            "mode": "deterministic_local",
            "model_required": False,
            "network_required": False,
            "scientific_execution_enabled": False,
        },
        "classification_status": classification["classification_status"],
        "needs_clarification": needs_clarification,
        "next_action": "ask_clarification" if needs_clarification else "prepare_plan",
        "clarification_question": clarification if needs_clarification else None,
        "routing_confidence": _confidence_level(confidence),
        "confidence_basis": classification["confidence_basis"],
        "routing_evidence": classification["routing_evidence"],
        "agent_assignments": assignments,
        "matched_domains": matched_domains,
        "steps": steps,
        "required_inputs": sorted(required),
        "scientific_gates": GATES,
        "disclaimer": disclaimer,
    }
