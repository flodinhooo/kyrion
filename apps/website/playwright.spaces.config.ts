import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "spaces-web.flow.ts",
  workers: 1,
  use: { baseURL: "http://127.0.0.1:3102", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node ../../infrastructure/spaces-ui-test-server.mjs",
    url: "http://127.0.0.1:3102/login",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
