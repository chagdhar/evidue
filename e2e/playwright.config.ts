import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:4173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      cwd: "..",
      command:
        "UV_CACHE_DIR=/tmp/evidue-uv-cache uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      cwd: "..",
      command: "npm --prefix frontend run dev -- --host 127.0.0.1 --port 4173",
      url: "http://127.0.0.1:4173/demo",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
