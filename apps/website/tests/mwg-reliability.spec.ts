import { test, expect, type Page, type Route } from "@playwright/test";

async function signedIn(page: Page) {
  await page.route("**/api/account/session", (r) =>
    r.fulfill({
      json: {
        enabled: true,
        session: {
          id: "mwg-a",
          csrf: "test",
          expiresAt: "2099-01-01T00:00:00Z",
        },
      },
    }),
  );
}
const snapshot = (name: string) => ({
  installations: [
    {
      id: "e2ef04ed-543a-451e-b9a8-cf72c08940de",
      name,
      spaceType: "HOME",
      localUsername: "fixture",
      linkedAt: "2026-11-12T12:00:00Z",
      confirmedAt: "2026-11-12T12:01:00Z",
    },
  ],
});

test("directory serializes slow reads and resumes from hidden tabs", async ({
  page,
}) => {
  await signedIn(page);
  await page.clock.install();
  const requests: Route[] = [];
  await page.route("**/api/account/installations", (route) => {
    requests.push(route);
  });
  await page.goto("/en/account");
  await expect.poll(() => requests.length).toBe(1);
  await page.clock.fastForward(10_000);
  await page.evaluate(() => {
    for (let i = 0; i < 5; i++) window.dispatchEvent(new Event("focus"));
  });
  expect(requests).toHaveLength(1);
  await requests[0].fulfill({ json: snapshot("First snapshot") });
  await expect(
    page.getByRole("heading", { name: "First snapshot", exact: true }),
  ).toBeVisible();
  await page.evaluate(() =>
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    }),
  );
  await page.clock.fastForward(10_000);
  expect(requests).toHaveLength(1);
  await page.evaluate(() => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    document.dispatchEvent(new Event("visibilitychange"));
  });
  await expect.poll(() => requests.length).toBe(2);
  await requests[1].fulfill({ json: snapshot("Current snapshot") });
  await expect(
    page.getByRole("heading", { name: "Current snapshot", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "First snapshot", exact: true }),
  ).toHaveCount(0);
});

test("directory times out without overlap and backs off after failure", async ({
  page,
}) => {
  await signedIn(page);
  await page.clock.install();
  let count = 0;
  await page.route("**/api/account/installations", async (r) => {
    count++;
    if (count > 1) await r.fulfill({ json: snapshot("Recovered snapshot") });
  });
  await page.goto("/en/account");
  await expect.poll(() => count).toBe(1);
  await page.clock.fastForward(15_001);
  await expect(page.locator('p[role="alert"]')).toContainText(
    "installation overview could not be loaded",
  );
  await page.clock.fastForward(9000);
  expect(count).toBe(1);
  await page.clock.fastForward(1100);
  await expect(
    page.getByRole("heading", { name: "Recovered snapshot", exact: true }),
  ).toBeVisible();
  expect(count).toBe(2);
});

test("session change aborts old directory reads and does not display old-user data", async ({
  page,
}) => {
  let id = "mwg-a",
    count = 0;
  await page.route("**/api/account/session", (r) =>
    r.fulfill({
      json: {
        enabled: true,
        session: { id, csrf: "fixture", expiresAt: "2099-01-01T00:00:00Z" },
      },
    }),
  );
  let oldRequest: Route | undefined;
  await page.route("**/api/account/installations", async (r) => {
    count++;
    if (count === 1) oldRequest = r;
    else await r.fulfill({ json: snapshot("Other user installation") });
  });
  await page.goto("/en/account");
  await expect.poll(() => !!oldRequest).toBe(true);
  const aborted = page.waitForEvent("requestfailed", (r) =>
    r.url().endsWith("/api/account/installations"),
  );
  id = "mwg-b";
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await aborted;
  await expect(
    page.getByRole("heading", { name: "Other user installation", exact: true }),
  ).toBeVisible();
  expect(count).toBe(2);
});

test("corrected text errors clear without submitting or validating untouched fields", async ({
  page,
}) => {
  let posts = 0;
  await page.route("**/api/contact", async (r) => {
    posts++;
    await r.fulfill({ json: { ok: true, code: "CONTACT_SENT" } });
  });
  for (const prefix of ["", "/en"]) {
    await page.goto(`${prefix}/contact`);
    const name = page.locator("#contact-name"),
      email = page.locator("#contact-email"),
      message = page.locator("#contact-message");
    await name.fill("Ada");
    await expect(message).toHaveAttribute("aria-invalid", "false");
    await page.locator('form button[type="submit"]').click();
    await expect(email).toHaveAttribute("aria-invalid", "true");
    await email.fill("still-invalid");
    await expect(email).toHaveAttribute("aria-invalid", "true");
    await email.fill("ada@example.com");
    await expect(email).toHaveAttribute("aria-invalid", "false");
    await expect(page.locator("#contact-email-error")).toHaveCount(0);
    await expect(message).toHaveAttribute("aria-invalid", "true");
    await message.fill("A valid corrected message.");
    await expect(message).toHaveAttribute("aria-invalid", "false");
    await expect(page.locator("#contact-message-error")).toHaveCount(0);
    await message.fill("");
    await expect(message).toHaveAttribute("aria-invalid", "false");
    await page.locator('form button[type="submit"]').click();
    await expect(message).toHaveAttribute("aria-invalid", "true");
  }
  expect(posts).toBe(0);
});
