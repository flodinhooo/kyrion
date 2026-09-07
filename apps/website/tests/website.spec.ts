import { expect, test } from "@playwright/test";

test("all public pages and translations render with metadata and no runtime errors", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const prefix of ["", "/de"]) {
    for (const route of ["", "/product", "/about", "/development", "/docs"]) {
      const path = `${prefix}${route}` || "/";
      const response = await page.goto(path);
      expect(response?.status()).toBe(200);
      await expect(page.locator("h1")).toHaveCount(1);
      await expect(page.locator("html")).toHaveAttribute(
        "lang",
        prefix ? "de" : "en",
      );
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
        "href",
        path === "/" ? "https://kyrion.ch" : `https://kyrion.ch${path}`,
      );
      await expect(page.locator('meta[property="og:image"]')).toHaveAttribute(
        "content",
        "https://kyrion.ch/branding/og-image.png",
      );
      expect(
        await page
          .locator("body")
          .evaluate((body) => body.scrollWidth <= window.innerWidth),
      ).toBe(true);
      if (!prefix)
        await page.screenshot({
          path: testInfo.outputPath(`${route.slice(1) || "home"}-light.png`),
          fullPage: true,
        });
    }
  }
  expect(errors).toEqual([]);
  expect((await page.goto("/does-not-exist"))?.status()).toBe(404);
});

test("theme follows the system, persists overrides and uses matching brand assets", async ({
  page,
}, testInfo) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  const html = page.locator("html");
  const appearance = page.getByRole("combobox", { name: "Appearance" });
  await expect(html).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("header .brand-dark")).toBeVisible();
  await expect(page.locator("header .brand-light")).toBeHidden();
  await page.screenshot({
    path: testInfo.outputPath("home-dark.png"),
    fullPage: true,
  });
  await appearance.selectOption("light");
  await expect(html).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "light");
  await expect(page.locator("header .brand-light")).toBeVisible();
  await appearance.selectOption("dark");
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "dark");
  await appearance.selectOption("system");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(html).toHaveAttribute("data-theme", "light");
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(html).toHaveAttribute("data-theme", "dark");
});

test("mobile navigation is keyboard accessible and closes on escape and navigation", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  const menu = page.getByRole("button", { name: "Open navigation" });
  await menu.focus();
  await page.keyboard.press("Enter");
  const panel = page.locator("#mobile-navigation");
  await expect(panel).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("mobile-menu.png") });
  await page.keyboard.press("Tab");
  await expect(
    panel.getByRole("link", { name: "Product", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  await expect(menu).toBeFocused();
  await menu.click();
  await panel.getByRole("link", { name: "Product", exact: true }).click();
  await expect(page).toHaveURL(/\/product$/);
  await expect(panel).toBeHidden();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await panel.getByRole("link", { name: "Sprache: Deutsch" }).click();
  await expect(page).toHaveURL(/\/de\/product$/);
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
});

test("small screens, reduced motion and generated assets remain usable", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const route of [
    "/",
    "/product",
    "/about",
    "/development",
    "/docs",
    "/de",
    "/de/product",
    "/de/about",
    "/de/development",
    "/de/docs",
  ]) {
    await page.goto(route);
    expect(
      await page
        .locator("body")
        .evaluate((body) => body.scrollWidth <= window.innerWidth),
    ).toBe(true);
  }
  expect(
    await page
      .locator("html")
      .evaluate((element) => getComputedStyle(element).scrollBehavior),
  ).toBe("auto");
  for (const asset of [
    "favicon.svg",
    "kyrion-light.svg",
    "kyrion-dark.svg",
    "og-image.png",
    "apple-touch-icon.png",
  ]) {
    const response = await request.get(`/branding/${asset}`);
    expect(response.status()).toBe(200);
    expect((await response.body()).length).toBeGreaterThan(100);
  }
});
