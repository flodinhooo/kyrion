import { expect, test } from "@playwright/test";

test("audience routes retain language, truthful status, contact and mobile navigation", async ({
  page,
  request,
}, testInfo) => {
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const locale of ["de", "en"]) {
      const prefix = locale === "en" ? "/en" : "";
      await page.goto(prefix || "/");
      const hero = page.locator("main > section").first();
      for (const audience of ["private", "business"]) {
        await expect(
          hero.locator(`a[href="${prefix}/${audience}"]`),
        ).toBeVisible();
        await page.goto(`${prefix}/${audience}`);
        await expect(page.locator("h1")).toHaveCount(1);
        await expect(page.locator("main")).toContainText(
          locale === "en" ? "not" : "nicht",
        );
        const contact = page
          .locator(`main a[href="${prefix}/contact"]`)
          .first();
        await expect(contact).toBeVisible();
        await expect(page.locator("main form")).toHaveCount(0);
        if (audience === "business") {
          await expect(page.locator("main")).toContainText("BUSINESS");
          await expect(page.locator("main")).toContainText(
            locale === "en"
              ? "not available business features"
              : "keine bereits verfügbaren Business-Funktionen",
          );
          await expect(page.locator("main")).toContainText(
            locale === "en" ? "isolation" : "Isolation",
          );
        } else {
          await expect(page.locator("main")).toContainText("PDF");
          await expect(page.locator("main")).toContainText(
            locale === "en" ? "Cloud AI is optional" : "Cloud-KI ist optional",
          );
        }
        await page.screenshot({
          path: testInfo.outputPath(`${locale}-${audience}-${width}.png`),
          fullPage: true,
        });
        const targetLocale = locale === "en" ? "de" : "en";
        await page
          .locator(`header a[hreflang="${targetLocale}"]`)
          .first()
          .click();
        await expect(page).toHaveURL(
          new RegExp(`${targetLocale === "en" ? "/en" : "3101"}/${audience}$`),
        );
        await page.goto(`${prefix}/${audience}`);
        if (width === 390) {
          await page
            .getByRole("button", {
              name: locale === "en" ? "Open navigation" : "Navigation öffnen",
            })
            .click();
          const link = page.locator(
            `#mobile-navigation a[href="${prefix}/${audience}"]`,
          );
          await expect(link).toHaveAttribute("aria-current", "page");
          await link.click();
          await expect(page.locator("#mobile-navigation")).toBeHidden();
        } else {
          await expect(
            page.locator(`header nav a[href="${prefix}/${audience}"]`).first(),
          ).toBeVisible();
        }
        await expect(
          page.locator(`footer a[href="${prefix}/${audience}"]`),
        ).toBeVisible();
        await contact.click();
        await expect(page).toHaveURL(new RegExp(`${prefix}/contact$`));
        await page.goto(prefix || "/");
      }
    }
  }
  const sitemap = await (await request.get("/sitemap.xml")).text();
  for (const path of ["/private", "/business", "/en/private", "/en/business"]) {
    expect(sitemap).toContain(`https://kyrion.ch${path}`);
  }
});
