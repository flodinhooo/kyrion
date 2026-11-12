import { defineConfig, devices } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

// Playwright's automatic failure DOM snapshots can contain password input values.
process.env.PLAYWRIGHT_NO_COPY_PROMPT = "1";

const settings = Object.fromEntries(
  readFileSync(
    path.resolve(__dirname, "../../.run/stabilization/identity-acceptance.env"),
    "utf8",
  )
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      const index = line.indexOf("=");
      return [line.slice(0, index), line.slice(index + 1)];
    }),
);

export default defineConfig({
  testDir: "./full-identity",
  workers: 1,
  expect: {timeout: 30_000},
  outputDir: "test-results/full-identity",
  timeout: 180_000,
  use: {
    trace: "off",
    screenshot: "off",
    video: "off",
    actionTimeout: 30_000,
    navigationTimeout: 45_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "node scripts/identity-acceptance-core.mjs",
      stdout: "pipe",
      url: "http://127.0.0.1:18092/actuator/health",
      reuseExistingServer: false,
      // Includes bounded DB/provider cold-start readiness before Core starts.
      timeout: 240_000,
    },
    {
      command: "pnpm exec next dev --port 3119 --hostname localhost",
      url: "http://localhost:3119/api/account/session",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        KYRION_BUILD_DIRECTORY: ".next-identity-full-website",
        KYRION_WEBSITE_ACCOUNT_ENABLED: "true",
        KYRION_WEBSITE_ACCOUNT_DEV_HTTP: "true",
        KYRION_WEBSITE_ORIGIN: "http://localhost:3119",
        KYRION_WEBSITE_OIDC_ISSUER: "http://localhost:18089/realms/kyrion",
        KYRION_WEBSITE_OIDC_CLIENT_ID: "kyrion-website",
        KYRION_WEBSITE_OIDC_CLIENT_SECRET: settings.WEBSITE_CLIENT_SECRET,
        KYRION_WEBSITE_ACCOUNT_DATABASE_URL: `postgresql://kyrion_website:${settings.WEBSITE_DB_PASSWORD}@127.0.0.1:15549/kyrion_website`,
      },
    },
    {
      command:
        "pnpm --dir ../web exec next dev --port 3219 --hostname localhost",
      url: "http://localhost:3219/login",
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        CORE_SERVICE_URL: "http://127.0.0.1:18092",
        KYRION_BUILD_DIRECTORY: ".next-identity-full-web",
      },
    },
  ],
});
