"""Browser-level user journeys against a real GEOLOGIA API process."""
import json

from playwright.sync_api import expect


def test_workspace_create_upload_inspect_plan_and_language(app_url, browser_page):
    page = browser_page
    page_errors = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    response = page.goto(app_url, wait_until="networkidle")
    assert response is not None and response.status == 200
    expect(page.locator("#apiStatus")).to_have_text("متصل")
    expect(page.locator("html")).to_have_attribute("dir", "rtl")
    expect(page.locator("#mapStatus")).to_contain_text("تعذر تحميل مكتبة الخريطة")

    page.locator("#projectName").fill("Sanaa groundwater basin")
    page.locator("#projectDescription").fill("Browser acceptance test")
    page.locator("#projectForm button[type=submit]").click()
    expect(page.locator("#projectStatus")).to_have_text("تم إنشاء المشروع.")
    project_id = page.locator("#projectSelect").input_value()
    assert project_id

    csv_content = "well_id,water_level_m,date\nW-01,125.4,2026-01-01\nW-02,126.1,2026-01-02\n"
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

    dataset.locator(".inspect-button:not(.validate-button)").click()
    report = dataset.locator(".inspection-report")
    expect(report).to_be_visible()
    report_text = report.inner_text()
    assert '"row_count": 2' in report_text
    assert '"column_count": 3' in report_text
    assert '"scientific_interpretation": false' in report_text

    dataset.locator(".validate-button").click()
    validation_report = dataset.locator(".validation-report")
    expect(validation_report).to_be_visible()
    validation_text = validation_report.inner_text()
    assert '"validation_status": "passed"' in validation_text
    assert '"groundwater-level-timeseries"' in validation_text
    assert '"scientific_interpretation": false' in validation_text

    request_text = "Assess groundwater level trends in the Sanaa basin"
    page.locator("#analysisRequest").fill(request_text)
    page.locator("#jobForm button[type=submit]").click()
    expect(page.locator("#jobStatus")).to_contain_text("تم حفظ خطة التحليل")
    plan_text = page.locator("#planOutput").inner_text()
    plan = json.loads(plan_text)
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
    page.goto(app_url, wait_until="networkidle")

    page.locator("#projectName").fill("CSV validation project")
    page.locator("#projectForm button[type=submit]").click()
    expect(page.locator("#projectStatus")).to_have_text("تم إنشاء المشروع.")

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

    dataset.locator(".validate-button").click()
    validation_report = dataset.locator(".validation-report")
    expect(validation_report).to_be_visible()
    expect(validation_report).to_contain_text('"validation_status": "failed"')
    expect(validation_report).to_contain_text("profile.timestamp.invalid")
    expect(page.locator("#uploadStatus")).to_have_class("feedback error")
