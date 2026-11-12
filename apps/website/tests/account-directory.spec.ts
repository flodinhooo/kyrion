import {test, expect} from "@playwright/test";
import {dictionaries} from "../src/lib/site";

test("linked installations are visible in the account overview and code entry has its own page", async ({
                                                                                                          page,
                                                                                                        }, info) => {
  await page.route("**/api/account/session", (r) =>
    r.fulfill({
      json: {
        enabled: true,
        session: {
          id: "directory-fixture",
          csrf: "fixture-csrf",
          expiresAt: new Date(Date.now() + 86400000).toISOString(),
        },
      },
    }),
  );
  await page.route("**/api/account/installations", (r) =>
    r.fulfill({
      json: {
        installations: [
          {
            id: "e2ef04ed-543a-451e-b9a8-cf72c08940de",
            name: "Kyrion Zuhause",
            spaceType: "HOME",
            localUsername: "florian-fixture",
            linkedAt: "2026-11-12T12:00:00Z",
            confirmedAt: "2026-11-12T12:01:00Z",
          },
        ],
      },
    }),
  );
  for (const locale of ["de", "en"] as const) {
    const t = dictionaries[locale].account,
      prefix = locale === "de" ? "" : "/en";
    await page.goto(`${prefix}/account`);
    await expect(
      page.getByRole("heading", {name: t.installationsTitle, exact: true}),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", {name: "Kyrion Zuhause", exact: true}),
    ).toBeVisible();
    await expect(
      page.getByText("florian-fixture", {exact: true}),
    ).toBeVisible();
    await page.setViewportSize({width: 360, height: 900});
    expect(
      await page.locator("body").evaluate((x) => x.scrollWidth <= innerWidth),
    ).toBe(true);
    if (locale === "de")
      await page.screenshot({
        path: info.outputPath("linked-installations-mobile.png"),
        fullPage: true,
      });
    await page.goto(`${prefix}/connect`);
    await expect(
      page.getByLabel(t.linkCodeLabel, {exact: true}),
    ).toBeVisible();
    await expect(
      page.locator('form[action="/api/account/connect"]'),
    ).toHaveAttribute("method", "post");
    await page.setViewportSize({width: 1280, height: 720});
  }
});
