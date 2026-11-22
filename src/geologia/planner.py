"""Model-independent, deterministic request routing for the Ali Algomori agent.

This module creates explainable plans only. It never runs a scientific engine,
downloads a model, calls a remote inference API, or manufactures a GIS fallback
when the request does not identify a geoscience domain.
"""
import re
import unicodedata

from geologia.normalize import normalize_text
from geologia.registry import ENGINES

INTENTS = [
    {
        "domain": "well_logs",
        "preferred_engines": ["lasio", "striplog"],
        "inputs": ["las_files", "well_header_metadata"],
        "keywords": [
            "las", "well log", "well logs", "petrophys", "porosity",
            "permeability", "gamma ray", "سجل البئر", "سجل الآبار",
            "سجلات الآبار", "سجلات البئر", "قطع الآبار", "قطع البئر",
            "المسامية", "النفاذية", "الشعاع الغامي",
        ],
    },
    {
        "domain": "hydrology",
        "preferred_engines": ["modflow6", "pastas"],
        "inputs": [
            "well_logs", "water_levels_timeseries", "recharge_estimate", "dem", "geology_map"
        ],
        "keywords": [
            "مياه", "المياه", "ماء", "الماء", "مياه جوفية", "المياه الجوفية",
            "جوفية", "الجوفية", "بئر", "آبار", "groundwater", "aquifer",
            "well", "pumping", "water table", "hydrogeology",
            "гидрогеология", "подземные воды", "водоносный горизонт",
            "скважина", "уровень воды", "地下水", "水文地质", "含水层", "水位", "水井",
        ],
    },
    {
        "domain": "geology3d",
        "preferred_engines": ["gempy", "loopstructural", "map2loop"],
        "inputs": ["geology_map", "structural_orientations", "contacts", "dem"],
        "keywords": [
            "ثلاثي", "طيات", "الفوالق", "فوالق", "مقطع جيولوجي", "3d",
            "cross section", "geological model", "structural geology",
            "трехмерная геологическая модель", "3d геология", "складки", "разломы",
            "геологический разрез", "三维地质", "地质建模", "褶皱", "断层", "地质剖面",
        ],
    },
    {
        "domain": "seismology",
        "preferred_engines": ["obspy", "openquake"],
        "inputs": ["waveforms_or_catalog", "station_metadata"],
        "keywords": [
            "زلزال", "زلازل", "الزلازل", "زلزالي", "seismic", "earthquake",
            "waveform", "ground motion", "землетрясение", "сейсмика", "сейсмология",
            "сейсмические волны", "地震", "地震学", "地震波", "地震目录",
        ],
    },
    {
        "domain": "geophysics",
        "preferred_engines": ["simpeg", "pygimli", "madagascar"],
        "inputs": ["geophysical_survey_data", "survey_geometry", "topography", "crs_definition"],
        "keywords": [
            "جيوفيزي", "كهرومغناطيسي", "مقاومة نوعية", "تصوير كهربائي",
            "جاذبية", "ثقالي", "مغناطيسي", "انعكاسي", "انكساري",
            "عكس جيوفيزيائي", "ert", "tomograph", "inversion", "resistivity",
            "magnetic", "gravity", "geophysic", "seismic reflection",
            "seismic refraction", "геофизика", "геофизический",
            "电法", "地球物理", "磁法", "重力勘探",
        ],
    },
    {
        "domain": "geochemistry",
        "preferred_engines": ["geochemistry-pi", "geopytool"],
        "inputs": ["geochemistry_samples", "sample_locations", "qc_report"],
        "keywords": [
            "جيوكيمي", "تحليل عنصري", "تحليل كيميائي للصخور", "عينات الصخور", "عينات",
            "geochemistry", "geochem", "elemental analysis", "rock classification",
            "геохимия", "геохимический анализ", "地球化学", "元素分析",
        ],
    },
    {
        "domain": "exploration",
        "preferred_engines": ["eis-toolkit"],
        "inputs": ["geochemistry_samples", "geophysics_surveys", "geology_map"],
        "keywords": [
            "ذهب", "الذهب", "معدن", "المعادن", "تنقيب", "استكشاف معدني",
            "gold", "mineral", "minerals", "exploration", "prospectivity",
            "золото", "минералы", "полезные ископаемые", "разведка",
            "金矿", "矿产", "矿物勘查", "找矿",
        ],
    },
    {
        "domain": "remote_sensing",
        "preferred_engines": ["opendronemap"],
        "inputs": ["imagery", "ground_control_points"],
        "keywords": [
            "درون", "استشعار عن بعد", "القمر الصناعي", "الأقمار الصناعية",
            "قمر صناعي", "صور فضائية", "drone", "satellite", "remote sensing",
            "photogrammetry", "дистанционное зондирование", "спутниковые снимки",
            "беспилотник", "фотограмметрия", "遥感", "卫星影像", "无人机", "摄影测量",
        ],
    },
    {
        "domain": "gis",
        "preferred_engines": ["geopandas", "rasterio", "qgis"],
        "inputs": ["aoi_boundary", "data_layers", "crs_definition"],
        "keywords": [
            "خريطة", "الخريطة", "خرائط", "طبقات", "نظم المعلومات الجغرافية",
            "gis", "map", "maps", "layers", "geographic information system",
            "геоинформационная система", "гис", "карта", "слои", "система координат",
            "地理信息系统", "地图", "图层", "坐标参考系",
        ],
    },
]

# Ali's preferred tools are advisory. The primary engine registry is the
# authoritative source for candidate IDs and their domains; registry entries
# remain planned/unverified and are never treated as installed integrations.
PRECEDENCE_RULES = [
    {
        "strong": "well_logs",
        "weak": "hydrology",
        "weak_generics": {normalize_text(k) for k in ("well", "بئر", "آبار")},
    },
    {
        "strong": "geophysics",
        "weak": "seismology",
        "weak_generics": {normalize_text(k) for k in ("seismic", "سيزمي", "زلزال", "زلازل")},
    },
]


def _prepare_intents(intents=None, registry=None) -> list[dict]:
    """Bind intent domains to the authoritative registry and fail on drift."""
    source_intents = INTENTS if intents is None else intents
    cards = ENGINES if registry is None else registry
    by_id = {card.get("engine_id"): card for card in cards}
    prepared = []
    for intent in source_intents:
        domain = intent["domain"]
        candidates = sorted(
            card["engine_id"] for card in cards if card.get("domain") == domain
        )
        if not candidates:
            raise RuntimeError(f"planner domain {domain!r} has no registered engines")
        preferred = list(intent.get("preferred_engines", []))
        for engine_id in preferred:
            card = by_id.get(engine_id)
            if card is None:
                raise RuntimeError(f"preferred engine {engine_id!r} is missing from registry")
            if card.get("domain") != domain:
                raise RuntimeError(
                    f"preferred engine {engine_id!r} belongs to {card.get('domain')!r}, "
                    f"not planner domain {domain!r}"
                )
        prepared.append({**intent, "candidate_engines": candidates})
    return prepared


PREPARED_INTENTS = _prepare_intents()
SUPPORTED_DOMAINS = [intent["domain"] for intent in PREPARED_INTENTS]

AGENT_ROLES = {
    "well_logs": ("well_log_specialist", "وكيل سجلات الآبار", "Well-log specialist"),
    "hydrology": ("groundwater_specialist", "وكيل المياه الجوفية", "Groundwater specialist"),
    "geology3d": ("geology3d_specialist", "وكيل النمذجة ثلاثية الأبعاد", "3D geology specialist"),
    "seismology": ("seismology_specialist", "وكيل الزلازل", "Seismology specialist"),
    "geophysics": ("geophysics_specialist", "وكيل الجيوفيزياء", "Geophysics specialist"),
    "geochemistry": ("geochemistry_specialist", "وكيل الجيوكيمياء", "Geochemistry specialist"),
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
CJK_ROUTING_PATTERN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
AGENT_NAME_EN = "Ali Algomori"


def agent_status() -> dict:
    """Describe the built-in agent without implying model training or engine execution."""
    return {
        "agent_id": AGENT_ID,
        "name_ar": AGENT_NAME_AR,
        "name_en": AGENT_NAME_EN,
        "supported_domains": list(SUPPORTED_DOMAINS),
        "architecture": "deterministic_rule_based",
        "runtime": "local",
        "model_required": False,
        "network_required": False,
        "scientific_execution_enabled": False,
        "capabilities": [
            "request_classification",
            "multilingual_ar_en_ru_zh_keyword_routing",
            "routing_evidence",
            "domain_routing",
            "registry_bound_engine_candidates",
            "well_log_geophysics_geochemistry_routing",
            "data_role_readiness",
            "explainable_plan_generation",
            "local_knowledge_retrieval",
        ],
        "limitations": [
            "No neural model is trained or loaded.",
            "No scientific engine is executed.",
            "Routing confidence is heuristic and not calibrated.",
            "A plan is not a scientific result or professional certification.",
            "External sources are not downloaded automatically.",
        ],
    }


def _normalize(text: str) -> str:
    """Normalize Unicode and Arabic spelling variants for keyword matching."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return normalize_text(text)

def _contains_phrase(normalized_text: str, keyword: str) -> bool:
    normalized_keyword = _normalize(keyword)
    if not normalized_keyword:
        return False
    if CJK_ROUTING_PATTERN.search(normalized_keyword):
        # CJK text commonly has no whitespace word boundaries.
        return normalized_keyword in normalized_text
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
        evidence = []
        evidence_norm = []
        for keyword in intent["keywords"]:
            normalized_keyword = _normalize(keyword)
            if _contains_phrase(normalized, normalized_keyword):
                evidence.append(keyword)
                evidence_norm.append(normalized_keyword)
        if evidence:
            matches.append({
                "domain": intent["domain"],
                "evidence": evidence,
                "matched_keywords_norm": evidence_norm,
                "confidence_level": _confidence_level(len(evidence)),
                "evidence_count": len(evidence),
            })

    # Suppress weak generic collisions only when all evidence for the weak
    # domain consists of its explicitly listed generic terms.
    by_domain = {item["domain"]: item for item in matches}
    for rule in PRECEDENCE_RULES:
        weak = by_domain.get(rule["weak"])
        strong = by_domain.get(rule["strong"])
        if (
            weak and strong
            and set(weak["matched_keywords_norm"]) <= rule["weak_generics"]
        ):
            matches.remove(weak)
            by_domain.pop(rule["weak"], None)
    if matches:
        for item in matches:
            item.pop("matched_keywords_norm", None)
        return {
            "classification_status": "matched",
            "needs_clarification": False,
            "matched_domains": [item["domain"] for item in matches],
            "routing_evidence": matches,
            "confidence_basis": (
                "distinct keyword evidence; confidence is heuristic, not calibrated"
            ),
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
        item = next(intent for intent in PREPARED_INTENTS if intent["domain"] == domain)
        evidence = evidence_by_domain[domain]
        steps.append({
            "domain": domain,
            "candidate_engines": item["candidate_engines"],
            "preferred_engines": item["preferred_engines"],
            "candidate_engine_status": "registry_only_not_installed_or_certified",
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
            "الزلازل، الجيوفيزياء، الجيوكيمياء، سجلات الآبار، استكشاف المعادن، "
            "الاستشعار عن بعد، أم نظم المعلومات الجغرافية؟"
        )
    else:
        disclaimer = (
            "Plan only: no engines ran and no scientific results were computed. "
            "No drilling or resource confirmation without sufficient data and scientific review."
        )
        clarification = (
            "Please specify the domain: groundwater, 3D geology, seismology, "
            "geophysics, geochemistry, well logs, mineral exploration, "
            "remote sensing, or GIS."
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
