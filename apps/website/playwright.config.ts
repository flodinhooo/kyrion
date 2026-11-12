import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  use: { baseURL: "http://127.0.0.1:3101", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer:
    process.env.PLAYWRIGHT_EXTERNAL_TEST_SERVER === "true"
      ? undefined
      : {
          command:
            "node ./node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3101",
          url: "http://127.0.0.1:3101",
          reuseExistingServer: false,
          timeout: 30_000,
          // Never send real mail from browser tests, even if a local .env is configured.
          env: {
            KYRION_WEBSITE_ACCOUNT_ENABLED: "false",
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
