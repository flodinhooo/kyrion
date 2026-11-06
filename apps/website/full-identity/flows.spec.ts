import { test, expect, type Page, type BrowserContext } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";
import { randomBytes } from "node:crypto";
import { execFileSync } from "node:child_process";
import { Pool } from "pg";

const root = path.resolve(__dirname, "../../..");
const settings = Object.fromEntries(
  readFileSync(
    path.join(root, ".run/stabilization/identity-acceptance.env"),
    "utf8",
  )
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      const index = line.indexOf("=");
      return [line.slice(0, index), line.slice(index + 1)];
    }),
);
const website = "http://localhost:3119";
const web = "http://localhost:3219";
const provider = "http://localhost:18089";
const core = "http://127.0.0.1:18092";
const pool = new Pool({
  connectionString: `postgresql://kyrion_acceptance:${settings.CORE_DB_PASSWORD}@127.0.0.1:15559/kyrion_acceptance`,
});

async function localLogin(page: Page, username: string) {
  await page.goto(`${web}/login`);
  await page.locator('input[name="username"]').fill(username);
  await page.locator('input[name="password"]').fill(settings.LOCAL_PASSWORD);
  await page
    .getByRole("button", { name: "Sign in locally", exact: true })
    .click();
  await expect(page).toHaveURL(`${web}/`);
}
async function webMutation(page: Page, endpoint: string, body: unknown = {}) {
  return page.evaluate(
    async ({ endpoint, body }) => {
      await fetch("/api/auth/csrf");
      const csrf =
        document.cookie
          .split("; ")
          .find((value) => value.startsWith("kyrion_csrf="))
          ?.split("=")[1] ?? "";
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "content-type": "application/json", "x-kyrion-csrf": csrf },
        body: JSON.stringify(body),
      });
      return {
        status: response.status,
        body: response.status === 204 ? null : await response.json(),
      };
    },
    { endpoint, body },
  );
}
async function me(context: BrowserContext) {
  const credential = (await context.cookies(web)).find(
    (cookie) => cookie.name === "kyrion_session",
  )?.value;
  const response = await fetch(`${core}/v1/auth/me`, {
    headers: { authorization: `Bearer ${credential}` },
  });
  expect(response.status).toBe(200);
  return response.json();
}
async function approveDevice(
  page: Page,
  context: BrowserContext,
  username: string,
  password: string,
) {
  const section = page.getByRole("region", {
    name: "Kyrion account",
    exact: true,
  });
  const userCode = (await section.locator("code").innerText()).trim();
  const href = await section
    .getByRole("link", { name: "Open Kyrion sign-in" })
    .getAttribute("href");
  if (!href || new URL(href).origin !== provider)
    throw new Error("Unexpected verification origin");
  const approval = await context.newPage();
  await approval.goto(href);
  await approval.locator('input[type="text"]').fill(userCode);
  await approval.locator('input[type="submit"],button[type="submit"]').click();
  if (await approval.locator("#password").isVisible()) {
    if (await approval.locator("#username").isVisible())
      await approval.locator("#username").fill(username);
    await approval.locator("#password").fill(password);
    await approval.locator("#kc-login").click();
  }
  await approval.getByRole("button", { name: /Yes|Confirm|Allow/i }).click();
  await approval.close();
}
function providerLifecycle(operation: "start" | "stop") {
  execFileSync(
    "docker",
    [
      "compose",
      "-p",
      "kyrion-identity-full",
      "--env-file",
      ".run/stabilization/identity-acceptance.env",
      "-f",
      "infrastructure/identity/acceptance.compose.yaml",
      operation,
      "keycloak",
    ],
    { cwd: root, stdio: "pipe" },
  );
}

test.afterAll(async () => {
  await pool.end();
});

test("real registration, verified email, website and local login/link/offline/unlink preserve Space rights", async ({
  browser,
}) => {
  test.setTimeout(360_000);
  const context = await browser.newContext({ locale: "en-US" });
  await context.addInitScript(() =>
    localStorage.setItem("kyrion-locale", "en"),
  );
  const page = await context.newPage();
  page.on("framenavigated", (frame) => {
    if (frame === page.mainFrame() && frame.url().startsWith("http")) {
      const url = new URL(frame.url());
      console.info(`Acceptance navigation: ${url.origin}${url.pathname}`);
    }
  });
  page.on("response", async (response) => {
    const route = new URL(response.url()).pathname;
    if (
      route === "/api/auth/central/poll" ||
      route === "/api/auth/central/complete"
    ) {
      try {
        const result = await response.json();
        const state = result.code ?? result.status ?? "completed";
        if (typeof state === "string" && /^[A-Z_]+$/.test(state))
          console.info(`Central response: ${response.status()} ${state}`);
      } catch {
        /* Page may navigate after completion; no response content is logged. */
      }
    }
  });
  const suffix = randomBytes(6).toString("hex");
  const centralUsername = `central-${suffix}`;
  const email = `${centralUsername}@acceptance.invalid`;
  const centralPassword = randomBytes(32).toString("base64url");

  await page.goto(`${website}/en/account`);
  await page
    .getByRole("button", { name: "Sign in with Kyrion Account", exact: true })
    .click();
  await page.getByRole("link", { name: "Register", exact: true }).click();
  await page.locator("#username").fill(centralUsername);
  await page.locator("#email").fill(email);
  await page.locator("#firstName").fill("Isolated");
  await page.locator("#lastName").fill("Acceptance");
  if (await page.locator("#password").count()) {
    await page.locator("#password").fill(centralPassword);
    await page.locator("#password-confirm").fill(centralPassword);
  }
  await page.getByRole("button", { name: "Register", exact: true }).click();
  if (await page.locator("#password-new").count()) {
    await page.locator("#password-new").fill(centralPassword);
    await page.locator("#password-confirm").fill(centralPassword);
    await page.locator('button[type="submit"],input[type="submit"]').click();
  }
  await expect(
    page.getByText(/verify your email|verify your email address/i).first(),
  ).toBeVisible();
  let messageId = "";
  await expect
    .poll(
      async () => {
        const response = await fetch("http://localhost:18025/api/v1/messages");
        const result = await response.json();
        messageId =
          result.messages.find((message: { To: { Address: string }[] }) =>
            message.To.some((recipient) => recipient.Address === email),
          )?.ID ?? "";
        return !!messageId;
      },
      { timeout: 30_000 },
    )
    .toBe(true);
  const mail = await (
    await fetch(`http://localhost:18025/api/v1/message/${messageId}`)
  ).json();
  const verification = String(mail.Text)
    .match(/http:\/\/localhost:18089\/[^\s<>]+/g)
    ?.find((value) => value.includes("action-token"));
  if (!verification)
    throw new Error("Mail catcher did not contain a local verification action");
  await page.goto(verification);
  if (await page.locator("#password-new").count()) {
    await page.locator("#password-new").fill(centralPassword);
    await page.locator("#password-confirm").fill(centralPassword);
    await page.getByRole("button", { name: "Submit", exact: true }).click();
  }
  await expect(
    page.getByText("You are signed in to the Kyrion website."),
  ).toBeVisible({ timeout: 30_000 });
  await page.getByRole("button", { name: "Sign out of this website" }).click();
  await page
    .getByRole("button", { name: "Sign in with Kyrion Account", exact: true })
    .click();
  if (await page.locator("#username").count())
    await page.locator("#username").fill(centralUsername);
  await page.locator("#password").fill(centralPassword);
  await page.locator("#kc-login").click();
  await expect(
    page.getByText("You are signed in to the Kyrion website."),
  ).toBeVisible();

  // Protected first setup uses the real existing UI and a host-provisioned proof.
  const setup = await (await fetch(`${core}/v1/auth/setup/status`)).json();
  if (setup.setupRequired) {
    await page.goto(`${web}/login`);
    await page.locator('input[name="username"]').fill("acceptance-owner");
    await page.locator('input[name="password"]').fill(settings.LOCAL_PASSWORD);
    await page
      .locator('input[name="passwordConfirmation"]')
      .fill(settings.LOCAL_PASSWORD);
    await page
      .locator('input[name="spaceName"]')
      .fill("Isolated identity acceptance");
    await page
      .locator('input[name="setupSecret"]')
      .fill(
        readFileSync(
          path.join(root, ".run/stabilization/identity-bootstrap.secret"),
          "utf8",
        ),
      );
    const invalidFields = await page.locator("form").evaluate((form) =>
      Array.from((form as HTMLFormElement).elements)
        .filter(
          (field) => field instanceof HTMLInputElement && !field.validity.valid,
        )
        .map((field) => (field as HTMLInputElement).name),
    );
    expect(invalidFields).toEqual([]);
    const submitted = page.waitForResponse(
      (response) =>
        new URL(response.url()).pathname === "/api/auth/setup" &&
        response.request().method() === "POST",
      { timeout: 30_000 },
    );
    await page.locator('button[type="submit"]').click();
    expect((await submitted).status()).toBe(201);
    await expect(page).toHaveURL(`${web}/`, { timeout: 30_000 });
  } else await localLogin(page, "acceptance-owner");
  const owner = await me(context);
  const invitation = await webMutation(page, "/api/auth/invitations");
  expect(invitation.status).toBe(201);
  expect((await webMutation(page, "/api/auth/logout")).status).toBe(204);
  const memberName = `member-${suffix}`;
  await page.goto(`${web}/signup#invitation=${invitation.body.code}`);
  await page.locator('input[name="username"]').fill(memberName);
  await page.locator('input[name="password"]').fill(settings.LOCAL_PASSWORD);
  await page
    .locator('input[name="passwordConfirmation"]')
    .fill(settings.LOCAL_PASSWORD);
  await page.locator('button[type="submit"]').click();
  await expect(page).toHaveURL(`${web}/`);
  const member = await me(context);
  expect(member.roles).not.toContain("OWNER");
  const counts = await pool.query(
    "SELECT (SELECT count(*) FROM user_account) AS users,(SELECT count(*) FROM rbac_user_role) AS roles",
  );
  expect((await webMutation(page, "/api/auth/logout")).status).toBe(204);

  // An authenticated but unlinked central identity cannot manufacture local access.
  await page.goto(`${web}/login`);
  await page
    .getByRole("button", { name: "Sign in with Kyrion account", exact: true })
    .click();
  await approveDevice(page, context, centralUsername, centralPassword);
  await page
    .getByRole("button", { name: "Continue to local application" })
    .click({ timeout: 45_000 });
  await expect(
    page
      .getByRole("region", { name: "Kyrion account", exact: true })
      .getByRole("alert"),
  ).toContainText("no linked local access");
  expect(
    (
      await pool.query(
        "SELECT (SELECT count(*) FROM user_account) AS users,(SELECT count(*) FROM rbac_user_role) AS roles",
      )
    ).rows,
  ).toEqual(counts.rows);

  await localLogin(page, memberName);
  await page.goto(`${web}/profile`);
  const panel = page.getByRole("region", {
    name: "Kyrion account",
    exact: true,
  });
  await panel
    .locator('input[name="currentPassword"]')
    .fill(settings.LOCAL_PASSWORD);
  await panel
    .getByRole("button", { name: "Connect Kyrion account", exact: true })
    .click();
  await approveDevice(page, context, centralUsername, centralPassword);
  await panel
    .getByRole("button", { name: "Confirm account connection" })
    .click({ timeout: 45_000 });
  await expect(
    panel.getByText("Your local account is connected."),
  ).toBeVisible();
  expect((await me(context)).permissions).toEqual(member.permissions);
  expect((await webMutation(page, "/api/auth/logout")).status).toBe(204);
  await page.goto(`${web}/login`);
  await page
    .getByRole("button", { name: "Sign in with Kyrion account", exact: true })
    .click();
  await approveDevice(page, context, centralUsername, centralPassword);
  await page
    .getByRole("button", { name: "Continue to local application" })
    .click({ timeout: 45_000 });
  await expect(page).toHaveURL(`${web}/`);
  const centralMe = await me(context);
  expect(centralMe.id).toBe(member.id);
  expect(centralMe.permissions).toEqual(member.permissions);
  expect(centralMe.roles).not.toContain("OWNER");

  // Real short provider token lifetime, no SQL expiry manipulation or fake clock.
  await expect
    .poll(
      async () => {
        await page.goto(`${web}/profile`);
        return new URL(page.url()).pathname;
      },
      { timeout: 85_000, intervals: [5000] },
    )
    .toBe("/login");
  await expect(
    page.getByRole("button", { name: "Sign in locally", exact: true }),
  ).toBeVisible();

  providerLifecycle("stop");
  try {
    await page
      .getByRole("button", { name: "Sign in with Kyrion account", exact: true })
      .click();
    await expect(
      page
        .getByRole("region", { name: "Kyrion account", exact: true })
        .getByRole("alert"),
    ).toContainText("currently unavailable", { timeout: 25_000 });
    await localLogin(page, memberName);
    expect((await me(context)).permissions).toEqual(member.permissions);
    await page.goto(`${web}/profile`);
    await expect(
      panel.getByText("Your local account is connected."),
    ).toBeVisible();
    await panel
      .locator('input[name="currentPassword"]')
      .fill(settings.LOCAL_PASSWORD);
    await panel.locator('input[name="confirm"]').check();
    await panel
      .getByRole("button", { name: "Disconnect Kyrion account", exact: true })
      .click();
    await expect(panel.getByText("No Kyrion account connected.")).toBeVisible();
    expect((await me(context)).id).toBe(member.id);
    expect(
      (
        await pool.query(
          "SELECT count(*) FROM central_identity_link WHERE user_id=$1",
          [member.id],
        )
      ).rows[0].count,
    ).toBe("0");
    expect(
      (
        await pool.query(
          "SELECT role_key FROM rbac_user_role ur JOIN rbac_role r ON r.id=ur.role_id WHERE ur.user_id=$1",
          [owner.id],
        )
      ).rows.map((row) => row.role_key),
    ).toContain("OWNER");
    expect((await webMutation(page, "/api/auth/logout")).status).toBe(204);
  } finally {
    providerLifecycle("start");
  }
  await page.goto(`${website}/en/account`);
  await expect(
    page.getByRole("button", {
      name: "Sign in with Kyrion Account",
      exact: true,
    }),
  ).toBeVisible();
  await context.close();
});
