import { test, expect } from "@playwright/test";
import { dictionaries } from "../src/lib/site";

const id = "11111111-1111-4111-8111-111111111111";
const inventory = {
  hasPassword: true,
  methods: [
    {
      id,
      kind: "passkey",
      label: "My laptop <not markup>",
      createdAt: 1700000000000,
      removable: true,
    },
    {
      id: "22222222-2222-4222-8222-222222222222",
      kind: "otp",
      label: "Protected authenticator",
      createdAt: null,
      removable: false,
    },
  ],
};

test("a late inventory from the previous session cannot reappear after account change", async ({
  page,
}) => {
  let user = "first";
  await page.route("**/api/account/session", (r) =>
    r.fulfill({
      json: {
        enabled: true,
        session: {
          id: user,
          csrf: user + "-csrf",
          expiresAt: new Date(Date.now() + 60000).toISOString(),
        },
      },
    }),
  );
  await page.route("**/api/account/installations", (r) =>
    r.fulfill({ json: { installations: [] } }),
  );
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let started!: () => void;
  const firstStarted = new Promise<void>((resolve) => {
    started = resolve;
  });
  let completed!: () => void;
  const firstCompleted = new Promise<void>((resolve) => {
    completed = resolve;
  });
  let reads = 0;
  await page.route("**/api/account/methods", async (r) => {
    if (++reads === 1) {
      started();
      await gate;
      try {
        await r.fulfill({ json: { inventory } });
      } catch {
        /* Aborted on session change. */
      } finally {
        completed();
      }
    } else
      await r.fulfill({
        json: { inventory: { methods: [], hasPassword: true } },
      });
  });
  await page.goto("/en/account");
  await firstStarted;
  await expect(
    page.getByText(dictionaries.en.account.methodsLoading, { exact: true }),
  ).toBeVisible();
  user = "second";
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect(
    page.getByText(dictionaries.en.account.methodsEmpty, { exact: true }),
  ).toBeVisible();
  release();
  await firstCompleted;
  await expect(
    page.getByText("My laptop <not markup>", { exact: true }),
  ).toHaveCount(0);
});

test("bilingual methods show names/dates, protect methods and require explicit confirmation", async ({
  page,
}) => {
  await page.route("**/api/account/session", (r) =>
    r.fulfill({
      json: {
        enabled: true,
        session: {
          id: "owner",
          csrf: "fixture-csrf",
          expiresAt: new Date(Date.now() + 60000).toISOString(),
        },
      },
    }),
  );
  await page.route("**/api/account/installations", (r) =>
    r.fulfill({ json: { installations: [] } }),
  );
  await page.route("**/api/account/methods", (r) =>
    r.fulfill({ json: { inventory } }),
  );
  for (const locale of ["de", "en"] as const) {
    const t = dictionaries[locale].account;
    await page.goto(`${locale === "en" ? "/en" : ""}/account`);
    const region = page.getByRole("region", { name: t.methodsTitle });
    await expect(
      region.getByRole("heading", {
        name: "My laptop <not markup>",
        exact: true,
      }),
    ).toBeVisible();
    await expect(region.locator("time")).toHaveAttribute(
      "datetime",
      new Date(1700000000000).toISOString(),
    );
    const row = region.locator("li").first();
    await row.locator("summary").click();
    const form = row.locator("form");
    await expect(form).toHaveAttribute("method", "post");
    await expect(form.locator('input[name="credentialId"]')).toHaveValue(id);
    await expect(form.locator('input[name="csrf"]')).toHaveValue(
      "fixture-csrf",
    );
    expect(
      await form.evaluate((f) => (f as HTMLFormElement).checkValidity()),
    ).toBe(false);
    await row.getByRole("checkbox").check();
    expect(
      await form.evaluate((f) => (f as HTMLFormElement).checkValidity()),
    ).toBe(true);
    await expect(region.locator("li").last().locator("summary")).toHaveCount(0);
    await expect(region.locator("li").last()).toContainText(t.methodProtected);
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await region.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }
});

test("inventory failure is distinct from empty and can be retried", async ({
  page,
}) => {
  await page.route("**/api/account/session", (r) =>
    r.fulfill({
      json: {
        enabled: true,
        session: {
          id: "owner",
          csrf: "csrf",
          expiresAt: new Date(Date.now() + 60000).toISOString(),
        },
      },
    }),
  );
  await page.route("**/api/account/installations", (r) =>
    r.fulfill({ json: { installations: [] } }),
  );
  let unavailable = true;
  await page.route("**/api/account/methods", (r) =>
    unavailable
      ? r.fulfill({ status: 503, json: { code: "ACCOUNT_UNAVAILABLE" } })
      : r.fulfill({ json: { inventory: { methods: [], hasPassword: true } } }),
  );
  const t = dictionaries.en.account;
  await page.goto("/en/account");
  await expect(
    page.getByText(t.methodsUnavailable, { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(t.methodsEmpty, { exact: true })).toHaveCount(0);
  unavailable = false;
  await page.getByRole("button", { name: t.methodsRetry, exact: true }).click();
  await expect(page.getByText(t.methodsEmpty, { exact: true })).toBeVisible();
});
