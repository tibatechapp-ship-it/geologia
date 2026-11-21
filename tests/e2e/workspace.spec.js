import { expect, test } from "@playwright/test";

async function createProject(page, name) {
  await page.goto("/");
  await page.locator("#projectName").fill(name);
  await page.locator("#projectDescription").fill("Browser end-to-end verification");
  await page.locator("#projectForm button[type=submit]").click();
  await expect(page.locator("#projectStatus")).toContainText("تم إنشاء المشروع.");
  await expect(page.locator("#projectSelect")).not.toHaveValue("");
}

test("creates a project and switches the workspace language", async ({ page }) => {
  await createProject(page, `Browser project ${Date.now()}`);

  await page.locator("#langToggle").click();

  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("heading", { name: "Projects" })).toBeVisible();
  await expect(page.locator("#projectSelect")).not.toHaveValue("");
});

test("uploads GeoJSON and displays a structural inspection report", async ({ page }) => {
  await createProject(page, `GeoJSON project ${Date.now()}`);

  const geojson = {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        properties: { station: "A-01", depth_m: 12.5 },
        geometry: { type: "Point", coordinates: [44.2, 15.3] },
      },
      {
        type: "Feature",
        properties: { station: "A-02", depth_m: 18 },
        geometry: { type: "Point", coordinates: [44.5, 15.8] },
      },
    ],
  };

  await page.locator("#datasetName").fill("Groundwater stations");
  await page.locator("#fileInput").setInputFiles({
    name: "stations.geojson",
    mimeType: "application/geo+json",
    buffer: Buffer.from(JSON.stringify(geojson)),
  });
  await page.locator("#datasetForm button[type=submit]").click();

  await expect(page.locator("#uploadStatus")).toContainText("تم حفظ البيانات");
  const inspectButton = page.getByRole("button", { name: "فحص GeoJSON" });
  await expect(inspectButton).toBeVisible();
  await inspectButton.click();

  const report = page.locator(".inspection-report");
  await expect(report).toContainText('"feature_count": 2');
  await expect(report).toContainText('"coordinate_count": 2');
  await expect(report).toContainText('"scientific_interpretation": false');
});

test("creates a plan without claiming scientific execution", async ({ page }) => {
  await createProject(page, `Planning project ${Date.now()}`);

  await page.locator("#analysisRequest").fill("Groundwater assessment for the study area");
  await page.locator("#jobForm button[type=submit]").click();

  await expect(page.locator("#jobStatus")).toContainText("تم حفظ خطة التحليل");
  await expect(page.locator("#planOutput")).toContainText('"plan_only": true');
  await expect(page.locator("#planOutput")).toContainText('"no_results_computed": true');
});
