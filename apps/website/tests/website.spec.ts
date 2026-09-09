import { expect, test } from "@playwright/test";

test("all public pages and translations render with metadata and no runtime errors", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  for (const prefix of ["", "/en"]) {
    for (const route of [
      "",
      "/product",
      "/about",
      "/development",
      "/docs",
      "/contact",
    ]) {
      const path = `${prefix}${route}` || "/";
      const response = await page.goto(path);
      expect(response?.status()).toBe(200);
      await expect(page.locator("h1")).toHaveCount(1);
      await expect(page.locator("html")).toHaveAttribute(
        "lang",
        prefix ? "en" : "de",
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
  await page.goto("/en");
  const html = page.locator("html");
  await expect(html).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("header .brand-dark")).toBeVisible();
  await expect(page.locator("header .brand-light")).toBeHidden();
  await page.emulateMedia({ colorScheme: "light" });
  await expect(html).toHaveAttribute("data-theme", "light");
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(html).toHaveAttribute("data-theme", "dark");
  await page.screenshot({
    path: testInfo.outputPath("home-dark.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Switch to light mode" }).click();
  await expect(html).toHaveAttribute("data-theme", "light");
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "light");
  await expect(page.locator("header .brand-light")).toBeVisible();
  const toggle = page.getByRole("button", { name: "Switch to dark mode" });
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(html).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "dark");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(html).toHaveAttribute("data-theme", "dark");
});

test("Velora voice preview follows the page language and stops on language change", async ({
  page,
  request,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(HTMLMediaElement.prototype, "play", {
      configurable: true,
      value: function () {
        Object.defineProperty(this, "paused", {
          configurable: true,
          value: false,
        });
        this.dispatchEvent(new Event("play"));
        return Promise.resolve();
      },
    });
    Object.defineProperty(HTMLMediaElement.prototype, "pause", {
      configurable: true,
      value: function () {
        Object.defineProperty(this, "paused", {
          configurable: true,
          value: true,
        });
        this.dispatchEvent(new Event("pause"));
      },
    });
  });
  await page.goto("/");
  for (const asset of [
    "/audio/velora-intro-de.mp3",
    "/audio/velora-intro-en.mp3",
  ]) {
    const response = await request.get(asset);
    expect(response.status()).toBe(200);
    expect(response.headers()["content-type"]).toContain("audio/mpeg");
    expect((await response.body()).length).toBeGreaterThan(10_000);
  }
  const audio = page.locator("audio");
  await expect(audio).toHaveAttribute("src", "/audio/velora-intro-de.mp3");
  const control = page.getByRole("button", { name: "Velora kennenlernen" });
  await expect(control).toBeVisible();
  await control.press("Enter");
  await expect(
    page.getByRole("button", { name: "Velora spricht" }),
  ).toBeVisible();
  await page.locator("audio").evaluate((element) => {
    element.dispatchEvent(new Event("ended"));
  });
  await expect(
    page.getByRole("button", { name: "Velora kennenlernen" }),
  ).toBeVisible();
  await page.locator('header a[hreflang="en"]').first().click();
  await expect(page).toHaveURL("http://127.0.0.1:3101/en");
  await expect(page.locator("audio")).toHaveAttribute(
    "src",
    "/audio/velora-intro-en.mp3",
  );
  await expect(page.getByRole("button", { name: "Meet Velora" })).toBeVisible();
});

test("mobile navigation is keyboard accessible and closes on escape and navigation", async ({
  page,
}, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/en");
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
  await expect(page).toHaveURL("http://127.0.0.1:3101/product");
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
    "/contact",
    "/en",
    "/en/product",
    "/en/about",
    "/en/development",
    "/en/docs",
    "/en/contact",
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

test("German is canonical, legacy URLs redirect and language links retain the page", async ({
  page,
  request,
}) => {
  for (const suffix of [
    "",
    "/product",
    "/about",
    "/development",
    "/docs",
    "/contact",
  ]) {
    const response = await request.get(`/de${suffix}`, { maxRedirects: 0 });
    expect(response.status()).toBe(308);
    expect(response.headers().location).toBe(suffix || "/");
  }
  await page.goto("/product");
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.locator('link[hreflang="x-default"]')).toHaveAttribute(
    "href",
    "https://kyrion.ch/product",
  );
  const english = page.locator('header a[hreflang="en"]').first();
  await expect(english).toContainText("EN");
  await expect(english.locator("svg")).toBeVisible();
  await english.click();
  await expect(page).toHaveURL("http://127.0.0.1:3101/en/product");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  const german = page.locator('header a[hreflang="de"]').first();
  await expect(german).toContainText("DE");
  await german.click();
  await expect(page).toHaveURL("http://127.0.0.1:3101/product");
  const sitemap = await request.get("/sitemap.xml");
  expect(await sitemap.text()).toContain("https://kyrion.ch/en/product");
  expect(await sitemap.text()).not.toContain("https://kyrion.ch/de/");
});
