import { expect, test, type Page } from "@playwright/test";

async function fillRequired(page: Page) {
  await page.getByLabel("Name *", { exact: true }).fill("Ada Example");
  await page.getByLabel("Email *", { exact: true }).fill("ada@example.com");
  await page
    .getByLabel("Subject *", { exact: true })
    .fill("A question about Kyrion");
  await page
    .getByLabel("Contact reason *", { exact: true })
    .selectOption("general");
  await page
    .getByLabel("Message *", { exact: true })
    .fill("I would like to learn more about the project.");
  await page.getByRole("checkbox", { name: /I agree that/ }).check();
}

test("contact validates required fields and invalid email inline", async ({
  page,
}) => {
  await page.goto("/en/contact");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.getByText("Please complete this required field."),
  ).toHaveCount(5);
  await expect(
    page.getByText(
      "Please acknowledge how your information may be used before sending.",
    ),
  ).toBeVisible();
  await expect(page.getByLabel("Name *", { exact: true })).toBeFocused();
  await fillRequired(page);
  await page.getByLabel("Email *", { exact: true }).fill("invalid-address");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.getByText("Enter a valid email address, such as name@example.com."),
  ).toBeVisible();
});

test("optional testing fields and successful submission prevent duplicate sends", async ({
  page,
}) => {
  let count = 0;
  let release: () => void = () => {};
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/contact", async (route) => {
    count++;
    const data = route.request().postDataJSON();
    expect(data).toMatchObject({
      reason: "testing",
      privacy: true,
      ecosystems: ["homeAssistant", "zigbee"],
    });
    await gate;
    await route.fulfill({ json: { ok: true, code: "CONTACT_SENT" } });
  });
  await page.goto("/en/contact");
  await expect(
    page.getByLabel("Country (optional)", { exact: true }),
  ).toHaveCount(0);
  await fillRequired(page);
  await page
    .getByLabel("Contact reason *", { exact: true })
    .selectOption("testing");
  await expect(
    page.getByLabel("Country (optional)", { exact: true }),
  ).toBeVisible();
  await page.getByRole("checkbox", { name: "None", exact: true }).check();
  await page
    .getByRole("checkbox", { name: "Home Assistant", exact: true })
    .check();
  await expect(
    page.getByRole("checkbox", { name: "None", exact: true }),
  ).not.toBeChecked();
  await page.getByRole("checkbox", { name: "Zigbee", exact: true }).check();
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sending…", exact: true }),
  ).toBeDisabled();
  await page.locator("form").evaluate((form) => {
    form.dispatchEvent(
      new Event("submit", { bubbles: true, cancelable: true }),
    );
  });
  release();
  await expect(
    page.getByRole("heading", { name: "Thank you for getting in touch." }),
  ).toBeVisible();
  expect(count).toBe(1);
  await expect(
    page.getByRole("button", { name: "Send message", exact: true }),
  ).toHaveCount(0);
});

test("delivery and network failures retain all entries", async ({ page }) => {
  await page.route("**/api/contact", (route) =>
    route.fulfill({
      status: 503,
      json: { ok: false, code: "CONTACT_DELIVERY_FAILED" },
    }),
  );
  await page.goto("/en/contact");
  await fillRequired(page);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.locator("form").getByRole("alert")).toContainText(
    "We couldn’t confirm delivery.",
  );
  await expect(page.getByLabel("Message *", { exact: true })).toHaveValue(
    "I would like to learn more about the project.",
  );
  await expect(page.getByLabel("Name *", { exact: true })).toHaveValue(
    "Ada Example",
  );
  await expect(
    page.getByRole("checkbox", { name: /I agree that/ }),
  ).toBeChecked();
  await page.unroute("**/api/contact");
  await page.route("**/api/contact", (route) => route.abort());
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.locator("form").getByRole("alert")).toContainText(
    "We couldn’t confirm delivery.",
  );
  await expect(page.getByLabel("Email *", { exact: true })).toHaveValue(
    "ada@example.com",
  );
});

test("contact works in both themes and German at narrow widths", async ({
  page,
}, testInfo) => {
  for (const colorScheme of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/contact");
    await page
      .getByLabel("Kontaktgrund *", { exact: true })
      .selectOption("testing");
    await expect(page.locator("html")).toHaveAttribute(
      "data-theme",
      colorScheme,
    );
    await expect(
      page.getByLabel("Land (optional)", { exact: true }),
    ).toBeVisible();
    expect(
      await page
        .locator("body")
        .evaluate((body) => body.scrollWidth <= innerWidth),
    ).toBe(true);
    await page.screenshot({
      path: testInfo.outputPath(`contact-${colorScheme}.png`),
      fullPage: true,
    });
  }
});

test("actual API rejects bots and fails safely without credentials", async ({
  request,
}) => {
  const headers = { origin: "http://127.0.0.1:3101" };
  const data = {
    name: "Test",
    email: "test@example.invalid",
    subject: "Test",
    reason: "general",
    message: "Local test",
    privacy: true,
  };
  const bot = await request.post("/api/contact", {
    headers,
    data: { ...data, website: "filled" },
  });
  expect(bot.status()).toBe(400);
  expect(await bot.json()).toMatchObject({ code: "CONTACT_REJECTED" });
  const unconfigured = await request.post("/api/contact", { headers, data });
  expect(unconfigured.status()).toBe(503);
  expect(await unconfigured.json()).toEqual({
    ok: false,
    code: "CONTACT_UNAVAILABLE",
  });
});
