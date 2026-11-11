import {expect, test} from "@playwright/test";

test("download pages show truthful availability and keep setup off the website", async ({
                                                                                          page,
                                                                                        }) => {
  for (const prefix of ["", "/en"]) {
    const response = await page.goto(`${prefix}/download`);
    expect(response?.status()).toBe(200);
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(
      page.locator("main form, main input, main select"),
    ).toHaveCount(0);
    await expect(
      page.locator('main a[href$=".exe"], main a[href$=".tar.gz"]'),
    ).toHaveCount(0);
    await expect(page.locator("main button[disabled]")).toHaveCount(0);
    await expect(page.locator('main a[href$="/hardware"]')).toBeVisible();
    await page.locator('main a[href$="/hardware"]').click();
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.getByText("Zigbee", {exact: true})).toBeVisible();
    await expect(page.getByText("Matter", {exact: true})).toBeVisible();
    await expect(page.getByText("Thread", {exact: true})).toBeVisible();
    await expect(
      page.locator("main form, main input, main select"),
    ).toHaveCount(0);
    expect(
      await page
        .locator("body")
        .evaluate((body) => body.scrollWidth <= innerWidth),
    ).toBe(true);
  }
});
