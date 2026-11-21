import json
from pathlib import Path

from geologia.planner import classify_request

CASES_PATH = Path(__file__).parent / "data" / "agent_routing_eval.json"


def test_curated_multilingual_routing_regression_suite():
    payload = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]
    assert len(cases) == 28
    assert len({case["id"] for case in cases}) == len(cases)

    errors = []
    for case in cases:
        result = classify_request(case["request"])
        actual = result["matched_domains"]
        expected = case["expected_domains"]
        if actual != expected:
            errors.append(
                f"{case['id']} ({case['language']}): expected {expected}, got {actual}"
            )
        if not expected and not result["needs_clarification"]:
            errors.append(f"{case['id']}: expected abstention")
        if expected and result["needs_clarification"]:
            errors.append(f"{case['id']}: incorrectly requested clarification")
        if expected and not result["routing_evidence"]:
            errors.append(f"{case['id']}: missing routing evidence")

    assert not errors, "\\n".join(errors)
