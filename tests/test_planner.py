import pytest

from geologia.planner import (
    PREPARED_INTENTS,
    _prepare_intents,
    agent_status,
    build_plan,
    classify_request,
)


def test_arabic_groundwater_request_routes_with_explicit_evidence():
    result = classify_request("أريد دراسة المياه الجوفية وتقييم منسوب الماء")
    assert result["classification_status"] == "matched"
    assert result["matched_domains"] == ["hydrology"]
    evidence = result["routing_evidence"][0]["evidence"]
    assert "المياه الجوفية" in evidence
    assert result["routing_evidence"][0]["confidence_level"] in {"medium", "high"}


def test_english_routing_is_case_and_punctuation_insensitive():
    result = classify_request("GROUNDWATER: evaluate the AQUifer and water table.")
    assert result["matched_domains"] == ["hydrology"]
    assert result["routing_evidence"][0]["confidence_level"] == "high"


def test_request_can_route_to_multiple_specialists():
    result = classify_request("Groundwater and inspect seismic ground motion")
    assert result["matched_domains"] == ["hydrology", "seismology"]


def test_unknown_request_does_not_fall_back_to_gis():
    plan = build_plan("Please analyze this area", language="en")
    assert plan["classification_status"] == "needs_clarification"
    assert plan["needs_clarification"] is True
    assert plan["next_action"] == "ask_clarification"
    assert plan["matched_domains"] == []
    assert plan["steps"] == []
    assert plan["required_inputs"] == []
    assert plan["clarification_question"]


def test_keyword_matching_uses_word_boundaries():
    result = classify_request("A wellbeing survey without geological context")
    assert result["matched_domains"] == []


def test_plan_exposes_evidence_and_keeps_execution_disabled():
    plan = build_plan("Groundwater assessment using well logs", language="en")
    assert plan["chief_agent"]["agent_id"] == "ali-algomori"
    assert plan["chief_agent"]["name_en"] == "Ali Algomori"
    assert plan["agent_runtime"]["mode"] == "deterministic_local"
    assert plan["agent_runtime"]["model_required"] is False
    assert plan["agent_runtime"]["network_required"] is False
    assert plan["routing_evidence"][0]["evidence"]
    assert plan["steps"][0]["routing_evidence"]
    assert plan["plan_only"] is True
    assert plan["no_results_computed"] is True


def test_agent_status_declares_capabilities_and_limits_honestly():
    status = agent_status()
    assert status["agent_id"] == "ali-algomori"
    assert status["model_required"] is False
    assert status["network_required"] is False
    assert status["scientific_execution_enabled"] is False
    assert "routing_evidence" in status["capabilities"]
    assert "multilingual_ar_en_ru_zh_keyword_routing" in status["capabilities"]
    assert "local_knowledge_retrieval" in status["capabilities"]
    assert any("not calibrated" in item for item in status["limitations"])

@pytest.mark.parametrize(
    ("query_text", "expected_domain"),
    [
        ("Изучить подземные воды и водоносный горизонт", "hydrology"),
        ("地下水与含水层评价", "hydrology"),
        ("三维地质建模和断层", "geology3d"),
        ("地震波与地震目录", "seismology"),
        ("矿物勘查与地球化学", "exploration"),
        ("遥感卫星影像", "remote_sensing"),
        ("地理信息系统与坐标参考系", "gis"),
    ],
)
def test_russian_and_chinese_domain_routing(query_text, expected_domain):
    result = classify_request(query_text)
    assert expected_domain in result["matched_domains"]
    matched = next(item for item in result["routing_evidence"]
                   if item["domain"] == expected_domain)
    assert matched["evidence"]
    assert result["needs_clarification"] is False


def test_multilingual_routing_keeps_source_terms_in_evidence():
    request = "地下水与水位，подземные воды"
    result = classify_request(request)
    hydro = next(item for item in result["routing_evidence"]
                 if item["domain"] == "hydrology")
    assert "地下水" in hydro["evidence"]
    assert "подземные воды" in hydro["evidence"]
    assert result["matched_domains"] == ["hydrology"]



def test_arabic_routing_ignores_diacritics_and_tatweel():
    result = classify_request("أريد دراسة المِيَاهُ الجَوْفِيَّة")
    assert result["classification_status"] == "matched"
    assert "hydrology" in result["matched_domains"]
    hydro = next(item for item in result["routing_evidence"]
                 if item["domain"] == "hydrology")
    assert "المياه الجوفية" in hydro["evidence"]


def test_arabic_routing_matches_hamza_and_alef_variants():
    result = classify_request("إِرْتِفَاع منسوب المياه")
    assert "hydrology" in result["matched_domains"]


def test_geochemistry_routes_to_its_registered_specialists():
    result = classify_request("Geochemistry sample analysis")
    assert result["matched_domains"] == ["geochemistry"]
    plan = build_plan("Geochemistry sample analysis", language="en")
    step = plan["steps"][0]
    assert step["domain"] == "geochemistry"
    assert set(step["candidate_engines"]) == {"geochemistry-pi", "geopytool"}
    assert set(step["preferred_engines"]) <= set(step["candidate_engines"])
    assert step["candidate_engine_status"] == "registry_only_not_installed_or_certified"


@pytest.mark.parametrize(
    ("query_text", "expected"),
    [
        ("Analyze geophysical resistivity inversion", "geophysics"),
        ("LAS well log porosity", "well_logs"),
        ("地球物理与电法", "geophysics"),
        ("地球化学与元素分析", "geochemistry"),
        ("Геофизика и магнитная разведка", "geophysics"),
        ("Геохимический анализ", "geochemistry"),
    ],
)
def test_added_ali_domains_route_multilingually(query_text, expected):
    result = classify_request(query_text)
    assert expected in result["matched_domains"]
    assert result["needs_clarification"] is False


def test_las_well_log_precedence_suppresses_generic_hydrology_match():
    result = classify_request("LAS well log porosity")
    assert result["matched_domains"] == ["well_logs"]


def test_geophysics_precedence_suppresses_generic_seismic_collision():
    result = classify_request("seismic reflection inversion")
    assert result["matched_domains"] == ["geophysics"]


def test_planner_candidates_are_derived_from_registry_domains():
    from geologia.registry import ENGINES

    registry_by_domain = {}
    for card in ENGINES:
        registry_by_domain.setdefault(card["domain"], set()).add(card["engine_id"])
    for intent in PREPARED_INTENTS:
        assert set(intent["candidate_engines"]) == registry_by_domain[intent["domain"]]
        assert set(intent["preferred_engines"]) <= registry_by_domain[intent["domain"]]


def test_preferred_engine_with_wrong_registry_domain_fails_closed():
    from geologia.registry import ENGINES

    with pytest.raises(RuntimeError, match="belongs to"):
        _prepare_intents(
            [{"domain": "exploration", "preferred_engines": ["geopytool"]}],
            registry=ENGINES,
        )


def test_planner_status_exposes_supported_registry_bound_domains():
    status = agent_status()
    assert {"well_logs", "geophysics", "geochemistry"} <= set(status["supported_domains"])
    result = classify_request("Groundwater")
    assert all("matched_keywords_norm" not in item for item in result["routing_evidence"])
