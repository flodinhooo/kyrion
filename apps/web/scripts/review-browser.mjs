// Run against the production build and a loopback-only fixture Core.
// No requests or mutations are sent to the owner's real Core or integrations.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const webDir = fileURLToPath(new URL("../", import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.REVIEW_PLAYWRIGHT_PATH || "playwright-core");
const artifacts = path.resolve(webDir, process.env.REVIEW_ARTIFACTS || "../../.run/release-review/browser");
await mkdir(artifacts, { recursive: true });
const date = "2026-09-05T10:00:00Z";
const room = { id: "11111111-1111-4111-8111-111111111111", name: "Wohnzimmer", roomType: "living_room", createdAt: date, updatedAt: date };
let rooms = [room];
let mode = "ready";
const requests = [];
const unexpected = new Set();
const device = { id: "22222222-2222-4222-8222-222222222222", provider: "zigbee", deviceClass: "light", displayName: "Leselampe", hardwareName: "Review light", room, capabilities: [{ id: "power.set" }], availability: "online", observedAt: date, state: { on: false, brightness: null, hue: null, saturation: null, colorTemperature: null, occupancy: null, battery: null, illuminance: null, action: null, illumination: null } };
const core = createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  requests.push(`${req.method} ${url.pathname}`);
  const send = (body, status = 200) => { res.writeHead(status, { "Content-Type": "application/json" }); res.end(JSON.stringify(body)); };
  if (mode === "down") return send({ code: "CORE_UNAVAILABLE" }, 503);
  if (url.pathname === "/v1/auth/setup/status") return send({ setupRequired: false });
  if (url.pathname === "/v1/auth/me") return mode === "expired" ? send({ code: "UNAUTHENTICATED" }, 401) : send({ id: "review-owner", username: "review" });
  if (url.pathname === "/v1/home/rooms" && req.method === "POST") {
    let body = ""; for await (const chunk of req) body += chunk;
    const input = JSON.parse(body);
    const created = { ...room, id: "33333333-3333-4333-8333-333333333333", ...input };
    rooms = [...rooms, created]; return send(created, 201);
  }
  if (url.pathname === "/v1/home/rooms") return send(rooms);
  if (url.pathname === "/v1/devices") return send(mode === "empty" ? [] : [device, { ...device, id: "44444444-4444-4444-8444-444444444444", displayName: "Offline sensor", deviceClass: "sensor", capabilities: [], availability: "offline", state: null }]);
  if (url.pathname === "/v1/device-commands/async") return send({ commandId: "review-command", deviceId: device.id, status: "pending" }, 202);
  if (url.pathname === "/v1/device-commands/review-command") return send({ id: "review-command", status: "succeeded", errorCode: null });
  if (url.pathname === "/v1/device-commands") return send({ capability: "light.power", roomName: room.name, requested: 1, succeeded: 1, failed: 0, outcomes: [{ deviceId: device.id, displayName: device.displayName, status: "succeeded" }], correlationId: "review-command" });
  if (url.pathname === "/v1/integrations/spotify") return send({ configured: true, connected: false, accountName: null });
  if (url.pathname === "/v1/integrations/spotify/playlists") return send({ reauthorizationRequired: false, items: [] });
  if (url.pathname === "/v1/integrations/spotify/playback") return send({ playing: false, title: null, artist: null, imageUrl: null, trackUrl: null, progressMs: 0, durationMs: 0, deviceId: null, disallowed: [] });
  if (["/v1/integrations/nanoleaf/connections", "/v1/gateways", "/v1/integrations/spotify/devices"].includes(url.pathname)) return send([]);
  if (url.pathname === "/v1/conversations") return send({ items: [{ id: "review-conversation", title: "Review conversation", createdAt: date, updatedAt: date }] });
  if (url.pathname === "/v1/activity") return send({ items: [] });
  unexpected.add(`${req.method} ${url.pathname}`);
  send({ code: "REVIEW_FIXTURE_UNSUPPORTED" }, 503);
});
await new Promise((resolve) => core.listen(0, "127.0.0.1", resolve));
const corePort = core.address().port;
const port = Number(process.env.REVIEW_WEB_PORT || 3107);
const origin = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, ["node_modules/next/dist/bin/next", "start", "--hostname", "127.0.0.1", "--port", String(port)], {
  cwd: webDir, windowsHide: true,
  env: { ...process.env, KYRION_BUILD_DIRECTORY: ".next-review", CORE_SERVICE_URL: `http://127.0.0.1:${corePort}`, AI_SERVICE_URL: "http://127.0.0.1:1", KYRION_PUBLIC_URL: origin, KYRION_INSECURE_LAN_HTTP: "true" },
  stdio: ["ignore", "pipe", "pipe"],
});
let serverOutput = "";
server.stdout.on("data", (data) => { serverOutput += data; });
server.stderr.on("data", (data) => { serverOutput += data; });
const results = [];
let browser;
try {
  for (let attempt = 0; ; attempt++) {
    try { if ((await fetch(`${origin}/login`)).ok) break; } catch { /* Wait for startup. */ }
    if (attempt >= 60 || server.exitCode !== null) throw new Error(`Review server failed: ${serverOutput.slice(-2000)}`);
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  browser = await chromium.launch({ executablePath: process.env.REVIEW_BROWSER || "C:/Program Files/Google/Chrome/Application/chrome.exe", headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: "de-DE" });
  await context.addCookies([{ name: "kyrion_session", value: "review-only", url: origin }, { name: "kyrion_csrf", value: "review-csrf", url: origin }]);
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const apiRequests = [];
  page.on("request", (request) => { if (request.url().includes("/api/")) apiRequests.push(new URL(request.url()).pathname); });
  const check = async (name, action) => {
    try { await action(); results.push({ name, passed: true }); console.log(`PASS ${name}`); }
    catch (error) { results.push({ name, passed: false, error: error.message }); console.log(`FAIL ${name}: ${error.message}`); await page.screenshot({ path: path.join(artifacts, `failure-${results.length}.png`) }).catch(() => {}); await writeFile(path.join(artifacts, `failure-${results.length}.html`), await page.content()); }
  };
  for (const viewport of process.env.REVIEW_QUICK ? [] : [{ width: 1440, height: 1000 }, { width: 390, height: 844 }, { width: 320, height: 568 }]) {
    await page.setViewportSize(viewport);
    for (const theme of ["light", "dark"]) {
      await page.goto(origin);
      await page.evaluate((theme) => { localStorage.setItem("kyrion-theme", theme); localStorage.setItem("kyrion-locale", "de"); }, theme);
      for (const route of ["/", "/devices", "/devices/add", "/plugins", "/plugins/nanoleaf", "/plugins/spotify", "/lounge", "/activity", "/automations", "/knowledge", "/profile", "/settings", "/settings/gateways", "/settings/services", "/settings/voice", "/settings/models", "/chat"]) {
        await check(`${viewport.width}/${theme}${route}`, async () => {
          const requestStart = apiRequests.length;
          await page.goto(`${origin}${route}`);
          await page.locator(".workspace").waitFor();
          await page.waitForTimeout(700);
          assert.equal(await page.locator("html").getAttribute("data-theme"), theme);
          assert.equal(await page.locator(".recent-section").count() > 0, route === "/chat");
          if (!["/chat", "/settings/models"].includes(route)) assert(!apiRequests.slice(requestStart).some((path) => ["/api/models", "/api/status", "/api/conversations"].includes(path)), "non-chat page requested AI/history");
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1 || document.querySelector(".workspace").scrollWidth > document.querySelector(".workspace").clientWidth + 1);
          assert(!overflow, "horizontal page overflow");
          await page.screenshot({ path: path.join(artifacts, `${viewport.width}-${theme}-${route.replaceAll("/", "_") || "home"}.png`) });
        });
      }
    }
  }
  await check("mobile navigation closes and returns focus", async () => {
    await page.setViewportSize({ width: 320, height: 568 });
    await page.goto(origin); await page.locator(".mobile-menu").click();
    await page.locator(".mobile-sheet").waitFor();
    await page.keyboard.press("Escape");
    await page.locator(".mobile-sheet").waitFor({ state: "hidden" });
    assert(await page.locator(".mobile-menu").evaluate((element) => element === document.activeElement));
  });
  await check("room creation through Web and Core boundary", async () => {
    await page.goto(origin);
    await page.locator(".home-actions button").first().click();
    await page.locator(".room-dialog input").fill("Review room");
    await page.locator(".room-dialog button[type=submit]").click();
    await page.locator(".plan-room", { hasText: "Review room" }).waitFor();
    assert(requests.includes("POST /v1/home/rooms"));
  });
  await check("device search empty state and reset", async () => {
    await page.goto(`${origin}/devices`);
    await page.locator(".device-search-field input").fill("does-not-exist");
    await page.getByText("Keine passenden Geräte", { exact: true }).waitFor();
    await page.getByRole("button", { name: "Filter zurücksetzen" }).first().click();
    await page.locator(".room-devices article").first().waitFor();
  });
  await check("Core failure preserves stale warning and recovers", async () => {
    await page.goto(origin); await page.locator(".snapshot-status time").waitFor(); mode = "down";
    await page.locator(".snapshot-status button").click();
    await page.locator(".snapshot-status [role=alert]").waitFor();
    mode = "ready"; await page.locator(".snapshot-status button").click();
    await page.locator(".snapshot-status [role=alert]").waitFor({ state: "hidden" });
  });
  await check("failed room write remains visible inside the dialog", async () => {
    await page.goto(origin); await page.locator(".home-actions button").first().click();
    await page.locator(".room-dialog input").fill("Interrupted room");
    await page.route("**/api/home/rooms", (route) => route.request().method() === "POST" ? route.abort("failed") : route.continue());
    await page.locator(".room-dialog button[type=submit]").click();
    await page.locator(".room-dialog [role=alert]").waitFor();
    assert(await page.locator(".room-dialog button[type=submit]").isEnabled());
    await page.unroute("**/api/home/rooms"); await page.keyboard.press("Escape");
  });
  await check("device power succeeds and a lost response stays retryable", async () => {
    await page.goto(`${origin}/devices`);
    const card = page.locator(".room-devices article", { hasText: "Leselampe" });
    const on = card.getByRole("button", { name: /Einschalten$/ });
    await on.click(); await page.waitForTimeout(500);
    assert(requests.includes("POST /v1/device-commands/async"));
    assert(await on.isEnabled());
    await page.route("**/api/device-commands/async", (route) => route.abort("failed"));
    await on.click(); await page.waitForTimeout(300); assert(await on.isEnabled());
    await page.unroute("**/api/device-commands/async");
  });
  await check("session expiry is visible on an already open page", async () => {
    await page.goto(origin); mode = "expired";
    await page.evaluate(() => window.dispatchEvent(new Event("focus")));
    await page.locator(".session-status[role=alert]").waitFor();
  });
  await check("expired session redirects to localized login", async () => {
    mode = "expired"; await page.goto(`${origin}/devices`); await page.waitForURL("**/login");
    await page.getByRole("heading", { name: "Bei Kyrion anmelden" }).waitFor();
    await page.locator(".language-button").click();
    await page.getByRole("heading", { name: "Sign in to Kyrion" }).waitFor();
  });
  await check("sign-in network failure stays actionable", async () => {
    await page.route("**/api/auth/login", (route) => route.abort("failed"));
    await page.getByLabel("Username", { exact: true }).fill("review");
    await page.getByLabel("Password", { exact: true }).fill("review-only-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await page.locator(".auth-error").waitFor();
    assert(await page.getByRole("button", { name: "Sign in", exact: true }).isEnabled());
  });
  await check("Core offline login offers retry", async () => {
    mode = "down"; await page.goto(`${origin}/login`);
    await page.locator(".auth-retry").waitFor();
    mode = "expired"; await page.locator(".auth-retry").click();
    await page.locator(".auth-form").waitFor();
  });
  await check("English workspace and keyboard skip link", async () => {
    mode = "ready"; await page.goto(origin);
    await page.waitForFunction(() => document.documentElement.lang === "en");
    await page.keyboard.press("Tab");
    assert(await page.locator(".skip-navigation").evaluate((element) => element === document.activeElement));
    await page.keyboard.press("Enter");
    assert(await page.locator(".workspace").evaluate((element) => element === document.activeElement));
  });
  await check("blocked preference storage does not crash the platform", async () => {
    await page.addInitScript(() => {
      Object.defineProperty(window, "speechSynthesis", { value: undefined, configurable: true });
      Storage.prototype.getItem = () => { throw new DOMException("blocked", "SecurityError"); };
      Storage.prototype.setItem = () => { throw new DOMException("blocked", "SecurityError"); };
    });
    await page.goto(origin); await page.locator(".snapshot-status time").waitFor();
    await page.locator(".topbar .language-button").click();
    await page.locator(".home-favorites-picker summary").click();
    await page.locator(".home-favorites-picker input").first().check();
    await page.locator(".home-favorites [role=status]").waitFor();
  });
  await check("no unhandled browser exceptions", async () => assert.deepEqual(errors, []));
  await writeFile(path.join(artifacts, process.env.REVIEW_QUICK ? "results-quick.json" : "results.json"), JSON.stringify({ results, unexpectedFixtureRequests: [...unexpected], errors }, null, 2));
  if (results.some((result) => !result.passed)) process.exitCode = 1;
} finally {
  await browser?.close(); server.kill(); core.closeAllConnections(); core.close();
  await writeFile(path.join(artifacts, "server.log"), serverOutput);
}
