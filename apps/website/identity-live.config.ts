import { defineConfig, devices } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const developmentSecrets = Object.fromEntries(
  readFileSync(
    path.resolve(__dirname, "../../infrastructure/identity/.env"),
    "utf8",
  )
    .split(/\r?\n/)
    .filter((line) => line && !line.startsWith("#"))
    .map((line) => {
      const index = line.indexOf("=");
      return [line.slice(0, index), line.slice(index + 1)];
    }),
);

export default defineConfig({
  testDir: "./identity-live",
  workers: 1,
  timeout: 90_000,
  use: {
    baseURL: "http://localhost:3109",
    trace: "off",
    screenshot: "off",
    video: "off",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "pnpm exec next dev --port 3109 --hostname localhost",
    url: "http://localhost:3109/api/account/session",
    reuseExistingServer: false,
    timeout: 90_000,
    env: {
      KYRION_WEBSITE_ACCOUNT_ENABLED: "true",
      KYRION_WEBSITE_ACCOUNT_DEV_HTTP: "true",
      KYRION_WEBSITE_ORIGIN: "http://localhost:3109",
      KYRION_WEBSITE_OIDC_ISSUER: "http://localhost:8089/realms/kyrion",
      KYRION_WEBSITE_OIDC_CLIENT_ID: "kyrion-website",
      KYRION_WEBSITE_OIDC_CLIENT_SECRET:
        developmentSecrets.WEBSITE_CLIENT_SECRET,
      KYRION_WEBSITE_ACCOUNT_DATABASE_URL: `postgresql://kyrion_website:${developmentSecrets.WEBSITE_DB_PASSWORD}@localhost:5549/kyrion_website`,
    },
  },
});
