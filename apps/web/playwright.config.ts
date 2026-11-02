import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  reporter: "list",
  use: { ...devices["Desktop Chrome"], baseURL: "http://127.0.0.1:3000" },
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:3000/lab",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { APP_ENV: "development", AUTH_MODE: "local" },
  },
});
