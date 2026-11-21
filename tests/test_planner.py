from geologia.planner import agent_status, build_plan, classify_request


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
    assert "local_knowledge_retrieval" in status["capabilities"]
    assert any("not calibrated" in item for item in status["limitations"])

@pytest.mark.parametrize(
    ("request", "expected_domain"),
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
def test_russian_and_chinese_domain_routing(request, expected_domain):
    result = classify_request(request)
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
