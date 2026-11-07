import { createRequire } from "node:module";
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const require = createRequire(path.join(root, "apps/website/package.json"));
const { chromium, expect: originalExpect } = require("@playwright/test");
const { Client } = require("pg");
const expect = originalExpect.configure({ timeout: 15_000 });
if (process.argv.length !== 3)
  throw new Error("Run through home-calendar-acceptance.mjs");
const fixture = JSON.parse(readFileSync(process.argv[2], "utf8"));
const run = fixture.run;
const base = fixture.webUrl;
assert.match(base, /^http:\/\/127\.0\.0\.1:\d+$/);
assert.match(fixture.coreUrl, /^http:\/\/127\.0\.0\.1:\d+$/);
assert.equal(fixture.database, "ky001_synthetic");
const db = new Client({
  host: "127.0.0.1",
  port: fixture.dbPort,
  database: fixture.database,
  user: "ky001",
  password: fixture.password,
});
const labels = {
  en: {
    create: "Create shared event",
    title: "Title",
    description: "Description",
    start: "Start",
    end: "End",
    save: "Save",
    cancel: "Cancel",
    remove: "Delete",
    refresh: "Refresh",
    month: "Month",
    week: "Week",
    day: "Day",
    conflict:
      "This event has changed. Refresh and reopen it before saving again.",
    readonly:
      "You can view this shared event; only its participants with editing permission can change it.",
  },
  de: {
    create: "Gemeinsamen Termin erstellen",
    title: "Titel",
    description: "Beschreibung",
    start: "Beginn",
    end: "Ende",
    save: "Speichern",
    cancel: "Abbrechen",
    remove: "Löschen",
    refresh: "Aktualisieren",
    month: "Monat",
    week: "Woche",
    day: "Tag",
    conflict:
      "Dieser Termin wurde inzwischen geändert. Bitte aktualisieren und vor dem Speichern erneut öffnen.",
    readonly:
      "Du kannst diesen gemeinsamen Termin sehen. Bearbeiten dürfen ihn nur Teilnehmer mit entsprechender Berechtigung.",
  },
};
const result = {
  baseline: fixture.sourceCommit,
  sourceDirty: fixture.sourceDirty,
  webSourceSha256: fixture.webSourceSha256,
  coreSha256: fixture.coreSha256,
  schema: fixture.version,
  postgresVersion: fixture.postgresVersion,
  postgresImage: fixture.postgresImage,
  providers:
    "No simulated providers; Google disconnected, no credentials, outbound proxy denies external HTTP(S)",
  cases: [],
  errors: [],
};
const browser = await chromium.launch({ headless: true });
result.browserVersion = browser.version();
result.nodeVersion = process.version;
const date = new Date().toISOString().slice(0, 7) + "-10";
async function api(page, endpoint, method = "GET", body) {
  return page.evaluate(
    async ({ endpoint, method, body }) => {
      const headers = {};
      if (method !== "GET") {
        await fetch("/api/auth/csrf");
        const csrf = document.cookie
          .split("; ")
          .find((v) => v.startsWith("kyrion_csrf="))
          ?.split("=")[1];
        headers["x-kyrion-csrf"] = csrf ?? "";
      }
      if (body !== undefined) headers["content-type"] = "application/json";
      const r = await fetch(endpoint, {
        method,
        headers,
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        cache: "no-store",
      });
      return {
        status: r.status,
        body: r.status === 204 ? null : await r.json(),
      };
    },
    { endpoint, method, body },
  );
}
async function login(page, username) {
  await page.goto(`${base}/login`);
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(fixture.accountPassword);
  await page.locator('form.auth-form button[type="submit"]').click();
  await expect(page).toHaveURL(`${base}/`);
  const me = await api(page, "/api/auth/me");
  assert.equal(me.status, 200);
  assert.equal(me.body.user.username, username);
}
const event = (page, title) =>
  page.locator(".fc-event").filter({ hasText: title }).first();
const form = (page) => page.locator("form.calendar-dialog");
async function calendar(page, text) {
  await page.goto(`${base}/calendar`);
  await expect(
    page.getByRole("button", { name: new RegExp(text.create) }),
  ).toBeVisible();
}
async function save(page, text, method, id) {
  const endpoint = `${base}/api/calendar/household-events${id ? "/" + id : ""}`;
  const before = await page.evaluate(
    () => window.ky001MutationResponses.length,
  );
  const response = page.waitForResponse(
    (r) => r.url() === endpoint && r.request().method() === method,
  );
  await form(page)
    .getByRole("button", { name: text.save, exact: true })
    .click();
  const network = await response;
  await page.waitForFunction(
    (index) => window.ky001MutationResponses.length > index,
    before,
  );
  const captured = await page.evaluate(
    (index) => window.ky001MutationResponses[index],
    before,
  );
  assert.equal(captured.url, endpoint);
  assert.equal(captured.method, method);
  assert.equal(captured.status, network.status());
  return { status: () => captured.status, json: async () => captured.body };
}
try {
  await db.connect();
  assert.equal(
    (await db.query("SELECT count(*)::int n FROM household_calendar_event"))
      .rows[0].n,
    0,
  );
  for (const locale of ["de", "en"])
    for (const [size, width, height] of [
      ["desktop", 1440, 1000],
      ["mobile", 390, 844],
    ]) {
      const key = `${locale}-${size}`,
        text = labels[locale];
      const row = { key, checks: [], passed: false };
      result.cases.push(row);
      const contexts = [];
      try {
        async function pageFor(user) {
          const ctx = await browser.newContext({
            locale: locale === "de" ? "de-CH" : "en-GB",
            timezoneId: "Europe/Zurich",
            viewport: { width, height },
          });
          contexts.push(ctx);
          await ctx.addInitScript(
            (locale) => localStorage.setItem("kyrion-locale", locale),
            locale,
          );
          // Observe the application's real response clone inside Chromium instead
          // of asking CDP for a body after a React navigation. No response is mocked.
          await ctx.addInitScript(() => {
            window.ky001MutationResponses = [];
            const original = window.fetch.bind(window);
            window.fetch = async (...args) => {
              const response = await original(...args);
              const method = args[1]?.method ?? "GET";
              if (
                ["POST", "PUT"].includes(method) &&
                response.url.includes("/api/calendar/household-events")
              ) {
                const body = await response.clone().json();
                window.ky001MutationResponses.push({
                  url: response.url,
                  method,
                  status: response.status,
                  body,
                });
              }
              return response;
            };
          });
          await ctx.route("**/*", (route) => {
            const u = new URL(route.request().url());
            if (["http:", "https:"].includes(u.protocol) && u.origin !== base) {
              result.errors.push(
                `External browser request denied: ${u.origin}`,
              );
              return route.abort();
            }
            return route.continue();
          });
          const page = await ctx.newPage();
          page.on("pageerror", (e) =>
            result.errors.push(`${key}: ${e.message}`),
          );
          if (user) await login(page, `ky001-${user}`);
          else await page.goto(`${base}/login`);
          return page;
        }
        const a = await pageFor("owner"),
          b = await pageFor("partner");
        const tokens = await Promise.all(
          [a, b].map(
            async (p) =>
              (await p.context().cookies()).find(
                (v) => v.name === "kyrion_session",
              )?.value,
          ),
        );
        assert.ok(tokens[0] && tokens[1] && tokens[0] !== tokens[1]);
        row.checks.push(
          "Actual separate password logins and distinct server sessions",
        );
        await calendar(a, text);
        await calendar(b, text);
        let title = `KY001 ${key} synthetic`;
        await a.getByRole("button", { name: new RegExp(text.create) }).click();
        await expect(
          form(a).getByLabel("ky001-owner", { exact: true }),
        ).toBeChecked();
        await expect(
          form(a).getByLabel("ky001-owner", { exact: true }),
        ).toBeDisabled();
        await form(a).getByLabel("ky001-partner", { exact: true }).check();
        await expect(
          form(a).getByLabel("ky001-observer", { exact: true }),
        ).not.toBeChecked();
        await expect(
          form(a).getByLabel("ky001-denied", { exact: true }),
        ).toHaveCount(0);
        await form(a).getByLabel(text.title, { exact: true }).fill(title);
        await form(a)
          .getByLabel(text.description, { exact: true })
          .fill("Synthetic acceptance only");
        await form(a)
          .getByLabel(text.start, { exact: true })
          .fill(`${date}T10:00`);
        await form(a)
          .getByLabel(text.end, { exact: true })
          .fill(`${date}T10:45`);
        const created = await save(a, text, "POST");
        assert.equal(created.status(), 201);
        const initial = await created.json();
        const id = initial.id;
        assert.deepEqual(
          initial.participantIds.sort(),
          [fixture.users.owner, fixture.users.partner].sort(),
        );
        await expect(form(a)).toHaveCount(0);
        await expect(event(a, title)).toBeVisible();
        await calendar(b, text);
        await expect(event(b, title)).toBeVisible();
        row.checks.push(
          "Explicit participant selection, actual Core create and visibility in both sessions",
        );
        await a.screenshot({
          path: path.join(run, `${key}-calendar.png`),
          fullPage: true,
        });

        await event(b, title).click();
        await expect(
          form(b).getByRole("button", { name: text.remove, exact: true }),
        ).toHaveCount(0);
        await form(b)
          .getByLabel(text.title, { exact: true })
          .fill(title + " partner");
        await form(b)
          .getByLabel(text.end, { exact: true })
          .fill(`${date}T11:00`);
        const updated = await save(b, text, "PUT", id);
        assert.equal(updated.status(), 200);
        const firstEdit = await updated.json();
        assert.equal(firstEdit.revision, 1);
        title += " partner";
        await calendar(a, text);
        await event(a, title).click();
        await expect(
          form(a).getByLabel(text.title, { exact: true }),
        ).toHaveValue(title);
        assert.equal(firstEdit.startsAt, initial.startsAt);
        assert.equal(
          Date.parse(firstEdit.endsAt) - Date.parse(firstEdit.startsAt),
          3600_000,
        );
        row.checks.push(
          "Second participant UI edit persisted, creator sees new revision, partner has no delete button",
        );

        await calendar(b, text);
        await event(b, title).click();
        await form(b)
          .getByLabel(text.title, { exact: true })
          .fill(title + " newer");
        const latest = await save(b, text, "PUT", id);
        assert.equal(latest.status(), 200);
        const secondEdit = await latest.json();
        assert.equal(secondEdit.revision, 2);
        await form(a)
          .getByLabel(text.title, { exact: true })
          .fill(title + " stale");
        const conflict = await save(a, text, "PUT", id);
        assert.equal(conflict.status(), 409);
        assert.equal(
          (await conflict.json()).code,
          "HOUSEHOLD_CALENDAR_CONFLICT",
        );
        await expect(form(a).getByRole("alert")).toHaveText(text.conflict);
        await expect(form(a).getByRole("alert")).toBeInViewport({ ratio: 1 });
        await a.screenshot({
          path: path.join(run, `${key}-conflict.png`),
          fullPage: true,
        });
        const persisted = await db.query(
          "SELECT title,revision FROM household_calendar_event WHERE id=$1",
          [id],
        );
        assert.equal(persisted.rows[0].title, title + " newer");
        assert.equal(Number(persisted.rows[0].revision), 2);
        row.checks.push(
          "Stale UI save gets actual 409 and localized conflict; database preserves latest accepted revision",
        );
        await form(a)
          .getByRole("button", { name: text.cancel, exact: true })
          .click();
        title += " newer";

        const body = {
          title: "forged synthetic edit",
          startsAt: secondEdit.startsAt,
          endsAt: secondEdit.endsAt,
          timeZone: "Europe/Zurich",
          revision: 2,
        };
        assert.equal(
          (
            await api(
              b,
              `/api/calendar/household-events/${id}?revision=2&retainExternalCopies=true`,
              "DELETE",
            )
          ).status,
          403,
        );
        const c = await pageFor("observer");
        await calendar(c, text);
        await event(c, title).click();
        await expect(form(c)).toHaveCount(0);
        await expect(c.getByText(text.readonly, { exact: true })).toBeVisible();
        assert.equal(
          (await api(c, `/api/calendar/household-events/${id}`, "PUT", body))
            .status,
          403,
        );
        assert.equal(
          (
            await api(
              c,
              `/api/calendar/household-events/${id}?revision=2&retainExternalCopies=true`,
              "DELETE",
            )
          ).status,
          403,
        );
        const d = await pageFor("denied");
        assert.equal((await api(d, "/api/calendar/events")).status, 403);
        assert.equal(
          (await api(d, "/api/calendar/household-events/members")).status,
          403,
        );
        assert.equal(
          (await api(d, `/api/calendar/household-events/${id}`, "PUT", body))
            .status,
          403,
        );
        const anonymous = await pageFor();
        assert.equal(
          (await api(anonymous, "/api/calendar/events")).status,
          401,
        );
        const still = await db.query(
          "SELECT title,revision FROM household_calendar_event WHERE id=$1",
          [id],
        );
        assert.equal(still.rows[0].title, title);
        assert.equal(Number(still.rows[0].revision), 2);
        row.checks.push(
          "Creator-only delete enforced server-side; nonparticipant reads household event but cannot edit/delete; no-calendar user 403; anonymous 401",
        );

        await calendar(a, text);
        for (const mode of [text.week, text.day, text.month])
          await a.getByRole("button", { name: mode, exact: true }).click();
        await expect(event(a, title)).toBeVisible();
        await event(a, title).click();
        a.once("dialog", (dialog) => dialog.accept());
        const removed = a.waitForResponse(
          (r) =>
            r.request().method() === "DELETE" &&
            r.url().includes(`/api/calendar/household-events/${id}?`),
        );
        await form(a)
          .getByRole("button", { name: text.remove, exact: true })
          .click();
        assert.equal((await removed).status(), 204);
        await expect(form(a)).toHaveCount(0);
        await expect(event(a, title)).toHaveCount(0);
        await calendar(b, text);
        await expect(event(b, title)).toHaveCount(0);
        assert.equal(
          (
            await db.query(
              "SELECT count(*)::int n FROM household_calendar_event WHERE id=$1",
              [id],
            )
          ).rows[0].n,
          0,
        );
        const audit = await db.query(
          "SELECT event_type,actor_id FROM activity_event WHERE summary_code=$1 AND event_type LIKE 'calendar.household.%' ORDER BY occurred_at",
          [id],
        );
        assert.deepEqual(
          audit.rows.map((v) => [v.event_type, v.actor_id]),
          [
            ["calendar.household.created", fixture.users.owner],
            ["calendar.household.updated", fixture.users.partner],
            ["calendar.household.updated", fixture.users.partner],
            ["calendar.household.deleted", fixture.users.owner],
          ],
        );
        row.checks.push(
          "Month/week/day controls; creator UI deletion removes event for both; actual actor audit verified in PostgreSQL",
        );
        assert.equal((await api(a, "/api/auth/logout", "POST")).status, 204);
        assert.equal((await api(a, "/api/calendar/events")).status, 401);
        const revoked = await fetch(`${fixture.coreUrl}/v1/auth/me`, {
          headers: { Authorization: `Bearer ${tokens[0]}` },
        });
        assert.equal(revoked.status, 401);
        assert.equal((await api(b, "/api/auth/me")).status, 200);
        await a.goto(`${base}/calendar`);
        await expect(a).toHaveURL(/\/login$/);
        row.checks.push(
          "Logout revokes own session and protected route redirects; partner session remains active",
        );
        row.passed = true;
        console.log(
          `PASS ${key}: ${row.checks.length} authenticated flow checkpoints`,
        );
      } finally {
        if (!row.passed)
          row.finalUrls = contexts.flatMap((ctx) =>
            ctx.pages().map((p) => p.url()),
          );
        for (const ctx of contexts) await ctx.close();
        writeFileSync(
          path.join(run, "browser-results.json"),
          JSON.stringify(result, null, 2),
        );
      }
    }
  const counts = await db.query(
    "SELECT (SELECT count(*)::int FROM integration_connection) connections,(SELECT count(*)::int FROM household_calendar_event) events,(SELECT count(*)::int FROM household_calendar_delivery) deliveries",
  );
  result.database = counts.rows[0];
  assert.equal(result.database.connections, 0);
  assert.equal(result.database.events, 0);
  assert.equal(result.database.deliveries, 0);
  assert.deepEqual(result.errors, []);
  result.passed = true;
} catch (error) {
  result.failure = error.message;
  console.error(error.stack);
  process.exitCode = 1;
} finally {
  await db.end();
  await browser.close();
  writeFileSync(
    path.join(run, "browser-results.json"),
    JSON.stringify(result, null, 2),
  );
}
