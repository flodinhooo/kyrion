import { expect, test } from "@playwright/test";

test("Home Business and Spaces describe local member administration in both languages", async ({
  page,
}) => {
  for (const prefix of ["", "/en"]) {
    await page.goto(`${prefix}/product`);
    await expect(
      page.getByRole("heading", {
        name: prefix
          ? "Home, Business and Kyrion Spaces"
          : "Home, Business und Kyrion Spaces",
      }),
    ).toBeVisible();
    await expect(
      page.getByText(
        prefix
          ? "Member administration and invitation acceptance happen"
          : "Mitgliederverwaltung und Einladungsannahme erfolgen",
        { exact: false },
      ),
    ).toBeVisible();
    await expect(
      page.locator('a[href*="portal.kyrion.ch"], a[href*="/login"]'),
    ).toHaveCount(0);
  }
});
