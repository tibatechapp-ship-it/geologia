from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB = ROOT / "src" / "geologia" / "web"


def test_plan_output_is_accessible_semantic_container():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    assert '<div id="planOutput" class="plan-output plan-output-cards" aria-live="polite">' in html
    assert '<pre id="planOutput"' not in html


def test_plan_renderer_uses_text_nodes_and_validates_external_citations():
    script = (WEB / "app.js").read_text(encoding="utf-8")
    assert "function renderPlan(plan)" in script
    assert "node.textContent=String(text)" in script
    assert 'url.protocol==="https:"' in script
    assert 'link.rel="noopener noreferrer"' in script
    assert 'JSON.stringify(job.plan,null,2)' not in script


def test_plan_renderer_exposes_scientific_limits_and_retrieval():
    script = (WEB / "app.js").read_text(encoding="utf-8")
    assert "knowledgeEvidence" in script
    assert "scientificBoundary" in script
    assert "requiredInputs" in script
    assert "routeEvidence" in script
    assert "currentPlan" in script
    styles = (WEB / "style.css").read_text(encoding="utf-8")
    assert ".plan-reference-card" in styles
    assert ".plan-missing-list" in styles
