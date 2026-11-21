import os from "node:os";
import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

const stateDir = path.join(os.tmpdir(), "geologia-playwright");

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
  },
  webServer: {
    command: "python -m uvicorn geologia.api:app --host 127.0.0.1 --port 8000",
    url: "http://127.0.0.1:8000/health",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
    env: {
      GEOLOGIA_DB_PATH: path.join(stateDir, "e2e.sqlite3"),
      GEOLOGIA_UPLOAD_DIR: path.join(stateDir, "uploads"),
    },
  },
});
