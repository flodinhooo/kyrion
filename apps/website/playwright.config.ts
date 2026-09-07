import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  use: { baseURL: "http://127.0.0.1:3101", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm exec next start --port 3101",
    url: "http://127.0.0.1:3101",
    reuseExistingServer: false,
    timeout: 30_000,
    // Never send real mail from browser tests, even if a local .env is configured.
    env: {
      CONTACT_FORM_ORIGIN: "http://127.0.0.1:3101",
      SMTP_HOST: "",
      SMTP_PORT: "",
      SMTP_USER: "",
      SMTP_PASSWORD: "",
      SMTP_FROM: "",
      CONTACT_EMAIL_TO: "",
    },
  },
});
