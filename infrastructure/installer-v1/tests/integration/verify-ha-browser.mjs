// Real local Web/Core routes against the isolated synthetic HA provider.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../../..",
);
const require = createRequire(path.join(root, "apps/website/package.json"));
const { chromium, expect } = require("@playwright/test");
let input = "";
for await (const part of process.stdin) {
  input += part;
  if (input.length > 4096) throw new Error("E_FIXTURE_INPUT");
}
const fixture = JSON.parse(input);
assert.match(fixture.webUrl, /^https:\/\/fixture\.test:\d+$/);
assert.match(fixture.session, /^[A-Za-z0-9_-]{32,256}$/);
const labels = {
  en: {
    preview: "Test connection and preview inventory",
    control: "Allow supported power control",
    room: "Room assignment",
    apply: "Review and save selection",
    success: "Selection imported and connection verified.",
    edit: "Update connection credentials",
    token: "Access token",
    rejected: "Home Assistant rejected the token.",
  },
  de: {
    preview: "Verbindung testen und Inventar anzeigen",
    control: "Unterstützte Ein-/Aus-Steuerung erlauben",
    room: "Raumzuordnung",
    apply: "Auswahl prüfen und speichern",
    success: "Auswahl importiert und Verbindung geprüft.",
    edit: "Verbindungsdaten aktualisieren",
    token: "Zugriffstoken",
    rejected: "Home Assistant hat den Token abgelehnt.",
  },
};
// This temporary test context accepts the disposable self-signed leaf only.
// The runner independently verifies TLS with its actual certificate using curl;
// no product trust store, browser profile or TLS setting is changed.
const browser = await chromium.launch({
  headless: true,
  args: [
    "--host-resolver-rules=MAP fixture.test 127.0.0.1",
    "--no-proxy-server",
  ],
});
const cases = [];
try {
  for (const locale of ["de", "en"])
    for (const width of [1440, 390]) {
      const t = labels[locale];
      const context = await browser.newContext({
        viewport: { width, height: 1000 },
        locale,
        ignoreHTTPSErrors: true,
      });
      try {
        await context.route("**/*", (route) =>
          route
            .request()
            .url()
            .startsWith(fixture.webUrl + "/")
            ? route.continue()
            : route.abort(),
        );
        await context.addCookies([
          {
            name: "kyrion_session",
            value: fixture.session,
            url: fixture.webUrl,
            httpOnly: true,
            secure: true,
            sameSite: "Lax",
          },
          {
            name: "kyrion_csrf",
            value: "c".repeat(43),
            url: fixture.webUrl,
            httpOnly: false,
            secure: true,
            sameSite: "Strict",
          },
        ]);
        await context.addInitScript(
          (value) => localStorage.setItem("kyrion-locale", value),
          locale,
        );
        const page = await context.newPage();
        const actions = [];
        page.on("request", (request) => {
          if (
            request.method() === "POST" &&
            request.url().includes("/api/device-commands")
          )
            actions.push(request.url());
        });
        await page.goto(fixture.webUrl + "/plugins/home_assistant");
        const card = page.locator(".ha-connection-card");
        await expect(
          card.getByRole("heading", { name: "Home Assistant", exact: true }),
        ).toBeVisible();
        await card
          .getByRole("button", { name: t.preview, exact: true })
          .click();
        const device = card.getByRole("group", {
          name: "Synthetic a",
          exact: true,
        });
        await expect(device).toBeVisible();
        await device
          .getByRole("checkbox", { name: "Synthetic a", exact: true })
          .check();
        await device
          .getByRole("checkbox", { name: "temperature (21)", exact: true })
          .uncheck();
        await device
          .getByRole("checkbox", { name: t.control, exact: true })
          .check();
        await device
          .getByRole("combobox", { name: t.room, exact: true })
          .selectOption("none");
        await card.getByRole("button", { name: t.apply, exact: true }).click();
        const dialog = page.getByRole("dialog");
        await expect(dialog).toBeVisible();
        await dialog
          .getByRole("button", { name: t.apply, exact: true })
          .click();
        await expect(card.getByText(t.success, { exact: true })).toBeVisible();
        const saved = await page.evaluate(async () => {
          const response = await fetch(
            "/api/integrations/home-assistant/selection",
            { cache: "no-store" },
          );
          return { status: response.status, value: await response.json() };
        });
        assert.equal(saved.status, 200);
        assert.equal(saved.value.devices.length, 1);
        assert.equal(saved.value.devices[0].entityKeys.length, 1);
        assert.equal(saved.value.devices[0].allowControl, true);
        assert.equal(saved.value.devices[0].overrideRoom, true);
        assert.equal(saved.value.devices[0].roomId, null);
        assert.deepEqual(actions, []);
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= window.innerWidth,
          ),
          true,
        );
        cases.push({
          locale,
          width,
          selected: true,
          consent: true,
          noDeviceAction: true,
        });
      } finally {
        await context.close();
      }
    }
  console.log(
    JSON.stringify({
      browserChecks: cases,
      provider: "synthetic-ha-only",
      productionDataUsed: false,
      browserTlsException: "temporary-disposable-test-context-only",
    }),
  );
} catch (error) {
  console.log(
    "E_HA_BROWSER_ASSERTION: " +
      String(error.message)
        .replaceAll(fixture.session, "<redacted>")
        .slice(0, 1500),
  );
  process.exitCode = 1;
} finally {
  await browser.close();
}
