import { expect, test, type Page } from "@playwright/test";

test.beforeEach(async ({ request, page }) => {
  await request.post("http://127.0.0.1:33081/fixture/reset");
  await page.addInitScript(() => localStorage.setItem("kyrion-locale", "en"));
});

async function setup(page: Page, type: "HOME" | "BUSINESS") {
  await page.goto("/login");
  await page
    .getByLabel("Space name")
    .fill(type === "HOME" ? "Our Home" : "Our Company");
  await page.getByLabel("Space type").selectOption(type);
  await page.getByLabel("Username", { exact: true }).fill("owner");
  await page.getByLabel("Password", { exact: true }).fill("test-only-password");
  await page
    .getByLabel("Confirm password", { exact: true })
    .fill("test-only-password");
  await page.locator('input[name="setupSecret"]').fill("S".repeat(43));
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL("/");
}

for (const type of ["HOME", "BUSINESS"] as const) {
  test(`${type} onboarding and local Space settings`, async ({ page }) => {
    await setup(page, type);
    await page.goto("/settings/space");
    await expect(page.getByLabel("Space name")).toHaveValue(
      type === "HOME" ? "Our Home" : "Our Company",
    );
    await expect(page.getByLabel("Space type")).toHaveValue(type);
    await page.getByLabel("Space name").fill("Updated Space");
    await page
      .getByRole("button", { name: "Save settings", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("Settings saved");
    if (type === "BUSINESS")
      await expect(
        page.getByRole("link", { name: "Identity and recovery" }),
      ).toBeVisible();
  });
}

test("invitation creation displays a local fragment link and supports revocation", async ({
  page,
}) => {
  await setup(page, "HOME");
  await page.goto("/settings/space");
  await page
    .getByRole("button", { name: "Create invitation", exact: true })
    .click();
  await expect(page.getByLabel("Invitation code", { exact: true })).toHaveValue(
    "I".repeat(43),
  );
  await expect(page.getByLabel("Invitation link", { exact: true })).toHaveValue(
    `http://127.0.0.1:3102/signup#invitation=${"I".repeat(43)}`,
  );
  page.on("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Revoke", exact: true }).click();
  await expect(page.getByText("Revoked", { exact: false })).toBeVisible();
});

test("invitation acceptance keeps the credential out of the URL and requires account creation", async ({
  page,
  context,
}) => {
  await setup(page, "HOME");
  await page.goto("/settings/space");
  await page
    .getByRole("button", { name: "Create invitation", exact: true })
    .click();
  await expect(
    page.getByLabel("Invitation code", { exact: true }),
  ).toBeVisible();
  await context.clearCookies();
  await page.goto(`/signup#invitation=${"I".repeat(43)}`);
  await expect(page).toHaveURL("/signup");
  await expect(page.locator('input[name="invitationCode"]')).toHaveValue(
    "I".repeat(43),
  );
  await page.locator('input[name="username"]').fill("new_member");
  await page.locator('input[name="password"]').fill("test-only-password");
  await page
    .locator('input[name="passwordConfirmation"]')
    .fill("test-only-password");
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL("/");
});

test("email status changes only after submitting the verification code", async ({
  page,
}) => {
  await setup(page, "BUSINESS");
  await page.goto("/settings/identity");
  await expect(
    page.getByText("No email identity", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Email address", { exact: true })
    .fill("member@company.ch");
  await page
    .getByRole("button", { name: "Send verification code", exact: true })
    .click();
  await expect(
    page.getByText("Awaiting mailbox verification", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Mailbox verified", { exact: true })).toHaveCount(
    0,
  );
  await page
    .getByLabel("Email verification code", { exact: true })
    .fill("V".repeat(43));
  await page.getByRole("button", { name: "Verify code", exact: true }).click();
  await expect(
    page.getByText("Mailbox verified", { exact: true }),
  ).toBeVisible();
});

test("Business policy explains DNS proof and rejects activation without recovery", async ({
  page,
}) => {
  await setup(page, "BUSINESS");
  await page.goto("/settings/identity");
  await page.goto("/chat");
  await expect(
    page.getByRole("button", {
      name: "Start Voice Mode with Velora",
      exact: true,
    }),
  ).toBeDisabled();
  await page.goto("/settings/identity");
  await page.getByLabel("Domain", { exact: true }).first().fill("company.ch");
  await page
    .getByRole("button", {
      name: "Create or rotate DNS challenge",
      exact: true,
    })
    .click();
  await expect(page.getByLabel("DNS TXT record name")).toHaveValue(
    "_kyrion-verification.company.ch",
  );
  await page.getByLabel("Enrollment policy").selectOption("STRICT");
  await page.getByRole("button", { name: "Save policy", exact: true }).click();
  await expect(page.locator(".auth-error[role=alert]")).toHaveText(
    "Provision local OWNER recovery first.",
  );
  await expect(
    page.getByText(
      "Host recovery must be provisioned before strict policy activation",
      { exact: true },
    ),
  ).toBeVisible();
});
