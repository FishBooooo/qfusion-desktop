import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:1420",
    trace: "on-first-retry",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: [
    {
      command: "../../.venv/bin/qfusion-backend",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      url: "http://127.0.0.1:8000/api/v1/health",
    },
    {
      command: "pnpm dev",
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      url: "http://127.0.0.1:1420",
    },
  ],
});
