import { defineConfig } from "@playwright/test";

const backendPort = 18001;
const frontendPort = 14173;

export default defineConfig({
  testDir: ".",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      cwd: "..",
      command:
        `UV_CACHE_DIR=/tmp/evidue-uv-cache uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port ${backendPort}`,
      url: `http://127.0.0.1:${backendPort}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      cwd: "..",
      command:
        `EVIDUE_API_URL=http://127.0.0.1:${backendPort} npm --prefix frontend run dev -- --host 127.0.0.1 --port ${frontendPort}`,
      url: `http://127.0.0.1:${frontendPort}/demo`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
