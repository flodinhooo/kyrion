// Real built local Web + Chromium; Core/auth are explicit loopback protocol doubles.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");
const require = createRequire(path.join(root, "apps/website/package.json"));
const { chromium, expect } = require("@playwright/test");
const health = {
  temperatureCelsius: null, throttled: null, memoryTotalBytes: 8192, memoryAvailableBytes: 4096,
  storageTotalBytes: 65536, storageAvailableBytes: 32768,
  ethernet: { present: null, connected: null }, wifi: { present: null, connected: null },
  ipv6: null, bluetooth: null, systemState: "unknown", adapters: [], audio: null,
  zigbee: null, bluetoothDevices: [], services: [],
};
const node = {
  id: "synthetic-node", displayName: "Synthetic unknown observations", hostname: "fixture",
  availability: "online", agentVersion: "0.2.0", osName: "Windows", osVersion: "fixture", architecture: "amd64",
  lastSeenAt: null, createdAt: "2026-11-24T00:00:00Z", health,
};
let mutations = 0;
const core = createServer((request, response) => {
  if (request.method !== "GET") { mutations++; response.writeHead(405).end(); return; }
  const value = request.url === "/v1/auth/me"
    ? { id: "synthetic-owner", username: "Fixture", roles: ["OWNER"], permissions: ["gateways:read"] }
    : request.url === "/v1/gateways" ? [node] : null;
  response.writeHead(value ? 200 : 404, { "Content-Type": "application/json" });
  response.end(JSON.stringify(value));
});
core.listen(0, "127.0.0.1");
await once(core, "listening");
const reservation = createServer();
reservation.listen(0, "127.0.0.1");
await once(reservation, "listening");
const port = reservation.address().port;
await new Promise((resolve) => reservation.close(resolve));
const base = "http://127.0.0.1:" + port;
const web = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "-H", "127.0.0.1", "-p", String(port)], {
  cwd: path.join(root, "apps/web"), windowsHide: true, stdio: "ignore",
  env: { ...process.env, CORE_SERVICE_URL: "http://127.0.0.1:" + core.address().port, NEXT_TELEMETRY_DISABLED: "1" },
});
let browser;
const cases = [];
try {
  let ready = false;
  for (let attempt = 0; attempt < 60; attempt++) {
    try { if ((await fetch(base + "/login", { signal: AbortSignal.timeout(3000) })).ok) { ready = true; break; } } catch { /* bounded readiness */ }
    if (web.exitCode !== null) throw new Error("E_BROWSER_FIXTURE_WEB_EXIT");
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  assert(ready);
  browser = await chromium.launch({ headless: true });
  for (const locale of ["de", "en"]) for (const theme of ["light", "dark"]) for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, locale });
    try {
      await context.addCookies([{ name: "kyrion_session", value: "synthetic-session", url: base, httpOnly: true }]);
      await context.addInitScript(({ locale, theme }) => {
        localStorage.setItem("kyrion-locale", locale);
        localStorage.setItem("kyrion-theme", theme);
      }, { locale, theme });
      await context.route("**/*", (route) => {
        const url = route.request().url();
        if (!url.startsWith(base + "/")) return route.abort();
        if (url.includes("/api/") && !url.endsWith("/api/gateways"))
          return route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
        return route.continue();
      });
      const page = await context.newPage();
      await page.goto(base + "/settings/gateways");
      const metrics = page.locator(".gateway-metrics");
      await expect(metrics.getByText(locale === "de" ? "Unbekannt" : "Unknown", { exact: true })).toHaveCount(5);
      await expect(page.getByText(locale === "de" ? /Leere Hardwarelisten bestätigen nicht/ : /Empty hardware lists do not confirm/)).toBeVisible();
      await page.keyboard.press("Tab");
      assert(await page.evaluate(() => document.activeElement !== document.body));
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
      cases.push({ locale, theme, width, unknownMetrics: 5, visibleUncertainty: true });
    } finally { await context.close(); }
  }
  assert.equal(mutations, 0);
  writeFileSync(path.join(root, "build/node-unknown-health-browser-report.json"), JSON.stringify({
    realBuiltWebAndChromium: true, syntheticCoreAndAuth: true, deviceActions: 0, cases,
  }, null, 2));
  console.log(JSON.stringify({ passedCases: cases.length, syntheticCoreAndAuth: true, deviceActions: 0 }));
} finally {
  if (browser) await browser.close();
  if (web.exitCode === null) { web.kill(); await once(web, "exit"); }
  await new Promise((resolve) => core.close(resolve));
}
