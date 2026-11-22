"""Browser acceptance tests for the GEOLOGIA workspace."""
import json

from playwright.sync_api import expect


def test_workspace_create_upload_inspect_plan_and_language(app_url, browser_page):
    page = browser_page
    page_errors = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    response = page.goto(app_url, wait_until="domcontentloaded")
    assert response is not None and response.status == 200
    expect(page.locator("#apiStatus")).to_contain_text("متصل")
    expect(page.locator("html")).to_have_attribute("dir", "rtl")

    page.locator("#projectName").fill("Sanaa groundwater basin")
    page.locator("#projectDescription").fill("Browser acceptance test")
    page.locator("#projectForm button[type=submit]").click()
    expect(page.locator("#projectStatus")).to_contain_text("تم إنشاء المشروع")
    project_id = page.locator("#projectSelect").input_value()
    assert project_id

    csv_content = (
        "well_id,water_level_m,date\n"
        "W-01,125.4,2026-01-01\n"
        "W-02,126.1,2026-01-02\n"
    )
    page.locator("#datasetName").fill("Groundwater levels")
    page.locator("#dataRole").select_option("water_levels_timeseries")
    page.locator("#fileInput").set_input_files(
        {
            "name": "water-levels.csv",
            "mimeType": "text/csv",
            "buffer": csv_content.encode("utf-8"),
        }
    )
    page.locator("#datasetForm button[type=submit]").click()
    dataset = page.locator(".dataset-item").filter(has_text="Groundwater levels")
    expect(dataset).to_be_visible()
    expect(page.locator("#datasetCount")).to_have_text("1")
    expect(page.locator("#uploadStatus")).to_contain_text("تم حفظ البيانات")

    dataset.locator("button.inspect-button").first.click()
    report = dataset.locator("pre.inspection-report")
    expect(report).to_be_visible()
    report_text = report.inner_text()
    assert '"row_count": 2' in report_text
    assert '"column_count": 3' in report_text
    assert '"scientific_interpretation": false' in report_text

    dataset.locator("button.provenance-button").click()
    provenance = dataset.locator("pre.provenance-report")
    expect(provenance).to_be_visible()
    provenance_text = provenance.inner_text()
    assert "سلامة سلسلة الأحداث" in provenance_text
    assert "سلامة الملف الحالي" in provenance_text
    assert "سلامة السجل لا تثبت صحة البيانات علميًا." in provenance_text
    provenance_data = json.loads(provenance_text[provenance_text.index("{"):])
    assert provenance_data["chain_integrity"] == "verified"
    assert provenance_data["content_integrity"] == "verified"

    request_text = "Assess groundwater level trends in the Sanaa basin"
    page.locator("#analysisRequest").fill(request_text)
    page.locator("#jobForm button[type=submit]").click()
    expect(page.locator("#jobStatus")).to_contain_text("تم حفظ خطة التحليل")
    jobs = page.evaluate(
        """async (projectId) => {
          const response = await fetch(
            "/api/v1/projects/" + encodeURIComponent(projectId) + "/jobs"
          );
          return response.json();
        }""",
        project_id,
    )
    assert jobs["count"] == 1
    plan = jobs["jobs"][0]["plan"]
    assert plan["plan_only"] is True
    assert plan["no_results_computed"] is True
    assert plan["data_readiness"]["content_validation"] == "not_performed"
    assert plan["data_readiness"]["execution_allowed"] is False

    page.locator("#langToggle").click()
    expect(page.locator("html")).to_have_attribute("lang", "en")
    expect(page.locator("html")).to_have_attribute("dir", "ltr")
    expect(page.locator("#langToggle")).to_have_text("عربي")
    expect(page.locator("#projectSelect")).to_have_value(project_id)

    assert page_errors == [], f"Uncaught browser exceptions: {page_errors}"


def test_malformed_csv_is_rejected_during_inspection(app_url, browser_page):
    page = browser_page
    page.goto(app_url, wait_until="domcontentloaded")

    page.locator("#projectName").fill("CSV validation project")
    page.locator("#projectForm button[type=submit]").click()
    expect(page.locator("#projectStatus")).to_contain_text("تم إنشاء المشروع")

    page.locator("#datasetName").fill("Malformed CSV")
    page.locator("#fileInput").set_input_files(
        {
            "name": "malformed.csv",
            "mimeType": "text/csv",
            "buffer": b'well_id,level\n"W-01,12.5\n',
        }
    )
    page.locator("#datasetForm button[type=submit]").click()
    dataset = page.locator(".dataset-item").filter(has_text="Malformed CSV")
    expect(dataset).to_be_visible()

    dataset.locator("button.inspect-button").first.click()
    expect(page.locator("#uploadStatus")).to_have_class("feedback error")
    expect(dataset.locator(".inspection-report")).to_have_count(0)



def test_geojson_upload_and_structural_inspection_are_explicit(app_url, browser_page):
    page = browser_page
    page.goto(app_url, wait_until="domcontentloaded")
    page.locator("#projectName").fill("GeoJSON structural inspection")
    page.locator("#projectForm button[type=submit]").click()
    expect(page.locator("#projectStatus")).to_contain_text("تم إنشاء المشروع")

    payload = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"station": "A-01", "depth_m": 12.5},
                "geometry": {"type": "Point", "coordinates": [44.2, 15.3]},
            },
            {
                "type": "Feature",
                "properties": {"station": "A-02", "depth_m": 18.0},
                "geometry": {"type": "Point", "coordinates": [44.5, 15.8]},
            },
        ],
    }
    page.locator("#datasetName").fill("Groundwater station points")
    page.locator("#fileInput").set_input_files(
        {
            "name": "stations.geojson",
            "mimeType": "application/geo+json",
            "buffer": json.dumps(payload).encode("utf-8"),
        }
    )
    page.locator("#datasetForm button[type=submit]").click()
    dataset = page.locator(".dataset-item").filter(
        has_text="Groundwater station points"
    )
    expect(dataset).to_be_visible()
    expect(page.locator("#uploadStatus")).to_contain_text("تم حفظ البيانات")

    dataset.locator("button.inspect-button").first.click()
    report = dataset.locator("pre.inspection-report")
    expect(report).to_be_visible()
    report_data = json.loads(report.inner_text().split("\n", 1)[1])
    assert report_data["feature_count"] == 2
    assert report_data["coordinate_count"] == 2
    assert report_data["bbox_xy"] == [44.2, 15.3, 44.5, 15.8]
    assert report_data["scientific_interpretation"] is False
