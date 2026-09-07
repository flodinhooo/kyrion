import { expect, test } from "@playwright/test";
import {
  validateContact,
  limits,
  type ContactPayload,
} from "../src/lib/contact/validation";
import { handleContact, MAX_BODY_BYTES } from "../src/lib/contact/handler";
import { buildContactEmail } from "../src/lib/contact/email";
import { readSmtpConfig, readContactOrigin } from "../src/lib/contact/config";

const valid = {
  name: " Ada Example ",
  email: " Ada@EXAMPLE.COM ",
  subject: " A question ",
  reason: "general",
  message: " Hello Kyrion.\r\nThank you. ",
  company: " Example organization ",
  privacy: true,
  website: "",
};
const origin = "https://kyrion.ch";
function request(body: unknown = valid, headers: Record<string, string> = {}) {
  return new Request(`${origin}/api/contact`, {
    method: "POST",
    headers: { origin, "content-type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
}

test("required fields and privacy acknowledgement are enforced", () => {
  for (const field of [
    "name",
    "email",
    "subject",
    "reason",
    "message",
    "privacy",
  ]) {
    for (const value of [undefined, "", false, null]) {
      const result = validateContact({ ...valid, [field]: value });
      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.fieldErrors).toHaveProperty(field);
    }
  }
  expect(validateContact({ ...valid, privacy: "true" }).ok).toBe(false);
  for (const body of [null, [], "payload", 42])
    expect(validateContact(body).ok).toBe(false);
});

test("malformed addresses, header injection and enum tampering are rejected", () => {
  for (const email of [
    "bad",
    "a@",
    "a@localhost",
    "a..b@example.com",
    "a@-example.com",
    "a@example..com",
    "Name <a@example.com>",
    "a@example.com,b@example.com",
    "a@example.com\r\nBcc: b@example.com",
    `${"a".repeat(65)}@example.com`,
  ]) {
    const result = validateContact({ ...valid, email });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.fieldErrors.email).toBeTruthy();
  }
  for (const field of ["name", "subject", "company", "country"])
    expect(
      validateContact({ ...valid, [field]: "value\r\nBcc: other@example.com" })
        .ok,
    ).toBe(false);
  for (const change of [
    { reason: "spam" },
    { experience: "invalid" },
    { ecosystems: "zigbee" },
    { ecosystems: ["unknown"] },
    { ecosystems: ["none", "zigbee"] },
    { message: "text\u0000text" },
  ])
    expect(validateContact({ ...valid, ...change }).ok).toBe(false);
});

test("all text limits are enforced and valid boundary lengths work", () => {
  for (const [field, max] of Object.entries(limits)) {
    const result = validateContact({ ...valid, [field]: "x".repeat(max + 1) });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.fieldErrors).toHaveProperty(field, "tooLong");
    if (field !== "email")
      expect(validateContact({ ...valid, [field]: "x".repeat(max) }).ok).toBe(
        true,
      );
  }
});

test("honeypots reject any content, including whitespace and non-strings", () => {
  for (const website of ["bot", " ", true, [], null]) {
    expect(validateContact({ ...valid, website })).toMatchObject({
      ok: false,
      code: "CONTACT_REJECTED",
    });
  }
});

test("valid payloads normalize text and optional testing details", () => {
  const result = validateContact({
    ...valid,
    name: " Jose\u0301 ",
    reason: " testing ",
    country: " Switzerland ",
    experience: " intermediate ",
    ecosystems: ["zigbee", "homeAssistant", "zigbee"],
  });
  expect(result).toEqual({
    ok: true,
    data: {
      name: "José",
      email: "Ada@example.com",
      subject: "A question",
      reason: "testing",
      message: "Hello Kyrion.\nThank you.",
      company: "Example organization",
      privacy: true,
      country: "Switzerland",
      experience: "intermediate",
      ecosystems: ["zigbee", "homeAssistant"],
    },
  });
  expect(validateContact({ ...valid, reason: "testing" }).ok).toBe(true);
  const ordinary = validateContact({
    ...valid,
    country: "Switzerland",
    experience: "advanced",
    ecosystems: ["zigbee"],
  });
  expect(ordinary).toMatchObject({
    ok: true,
    data: { country: "", experience: "", ecosystems: [] },
  });
});

test("email renders readable text and escaped HTML without visitor-controlled routing", () => {
  const result = validateContact({
    ...valid,
    reason: "testing",
    country: "CH",
    experience: "beginner",
    ecosystems: ["homeAssistant"],
    name: "<b>Ada & Co</b>",
    message: '<img src="https://example.com">\nA & B',
    bcc: "other@example.com",
  });
  if (!result.ok) throw new Error("Fixture invalid");
  const email = buildContactEmail(result.data, "test-reference");
  expect(email.html).toContain("&lt;b&gt;Ada &amp; Co&lt;/b&gt;");
  expect(email.html).not.toContain("<img");
  expect(email.text).toContain('<img src="https://example.com">');
  expect(email.text).toContain("Smart-home ecosystem:\nHome Assistant");
  expect(email.text).toContain("Company / organization:\nExample organization");
  expect(email.replyTo.address).toBe("Ada@example.com");
  expect(email).not.toHaveProperty("bcc");
  expect(email).not.toHaveProperty("to");
});

test("SMTP configuration requires all variables and verified encryption", () => {
  expect(readContactOrigin({ CONTACT_FORM_ORIGIN: "https://kyrion.ch/" })).toBe(
    "https://kyrion.ch",
  );
  expect(
    readContactOrigin({ CONTACT_FORM_ORIGIN: "http://localhost:3001" }),
  ).toBe("http://localhost:3001");
  for (const value of [
    "",
    "http://kyrion.ch",
    "https://kyrion.ch/contact",
    "https://user:password@kyrion.ch",
    "https://kyrion.ch?query=1",
  ])
    expect(() => readContactOrigin({ CONTACT_FORM_ORIGIN: value })).toThrow();
  const env = {
    SMTP_HOST: "mail.infomaniak.com",
    SMTP_PORT: "465",
    SMTP_USER: "mailbox@example.invalid",
    SMTP_PASSWORD: "test-only-value",
    SMTP_FROM: "mailbox@example.invalid",
    CONTACT_EMAIL_TO: "recipient@example.invalid",
  };
  expect(readSmtpConfig(env).transport).toMatchObject({
    port: 465,
    secure: true,
    requireTLS: true,
    tls: { minVersion: "TLSv1.2", rejectUnauthorized: true },
    logger: false,
    debug: false,
    disableFileAccess: true,
    disableUrlAccess: true,
  });
  expect(readSmtpConfig({ ...env, SMTP_PORT: "587" }).transport).toMatchObject({
    port: 587,
    secure: false,
    requireTLS: true,
  });
  for (const key of Object.keys(env))
    expect(() => readSmtpConfig({ ...env, [key]: "" })).toThrow(
      "Contact delivery is not configured",
    );
  for (const port of ["25", "0", "465x", "465.0"])
    expect(() => readSmtpConfig({ ...env, SMTP_PORT: port })).toThrow();
  expect(() =>
    readSmtpConfig({
      ...env,
      CONTACT_EMAIL_TO: "one@example.com,two@example.com",
    }),
  ).toThrow();
});

test("request boundary rejects cross-origin, malformed and oversized submissions without delivery", async () => {
  let deliveries = 0;
  const deps = {
    getAllowedOrigin: () => origin,
    deliver: async () => {
      deliveries++;
    },
    logFailure: () => {},
  };
  const cases: [Request, number][] = [
    [request(valid, { origin: "https://other.example" }), 403],
    [request(valid, { origin: "" }), 403],
    [request(valid, { "sec-fetch-site": "cross-site" }), 403],
    [request(valid, { "content-type": "text/plain" }), 415],
    [request({}), 400],
    [request({ ...valid, website: "bot" }), 400],
    [request({ ...valid, message: "x".repeat(MAX_BODY_BYTES) }), 413],
    [request(valid, { "content-length": String(MAX_BODY_BYTES + 1) }), 413],
    [
      new Request(`${origin}/api/contact`, {
        method: "POST",
        headers: { origin, "content-type": "application/json" },
        body: "{broken",
      }),
      400,
    ],
  ];
  for (const [req, status] of cases)
    expect((await handleContact(req, deps)).status).toBe(status);
  expect(deliveries).toBe(0);
});

test("successful delivery receives only normalized fields and is awaited", async () => {
  let resolveSend: () => void = () => {};
  const send = new Promise<void>((resolve) => {
    resolveSend = resolve;
  });
  let received: ContactPayload | undefined;
  let finished = false;
  const result = handleContact(request(), {
    getAllowedOrigin: () => origin,
    deliver: async (data, id) => {
      received = data;
      expect(id).toMatch(/^[a-f0-9-]{36}$/);
      await send;
    },
    logFailure: () => {},
  }).then((response) => {
    finished = true;
    return response;
  });
  await expect.poll(() => received?.name).toBe("Ada Example");
  expect(finished).toBe(false);
  resolveSend();
  const response = await result;
  expect(response.status).toBe(200);
  expect(response.headers.get("cache-control")).toBe("no-store");
  expect(await response.json()).toEqual({ ok: true, code: "CONTACT_SENT" });
  expect(received).toMatchObject({
    email: "Ada@example.com",
    subject: "A question",
    message: "Hello Kyrion.\nThank you.",
  });
  expect(received).not.toHaveProperty("website");
});

test("mail failure is generic, logs no content and does not retry", async () => {
  const events: unknown[] = [];
  let attempts = 0;
  const response = await handleContact(request(), {
    getAllowedOrigin: () => origin,
    deliver: async () => {
      attempts++;
      throw Object.assign(new Error("sensitive provider detail"), {
        code: "EAUTH",
      });
    },
    logFailure: (event) => events.push(event),
  });
  expect(response.status).toBe(503);
  expect(await response.json()).toEqual({
    ok: false,
    code: "CONTACT_DELIVERY_FAILED",
  });
  expect(attempts).toBe(1);
  expect(events).toEqual([
    {
      event: "contact_delivery_failed",
      requestId: expect.any(String),
      category: "authentication",
    },
  ]);
  expect(JSON.stringify(events)).not.toContain("sensitive");
  expect(JSON.stringify(events)).not.toContain("Ada");
});

test("unconfigured mail and future abuse-policy rejection fail closed", async () => {
  const config = await handleContact(request(), {
    getAllowedOrigin: () => origin,
    deliver: async () => {
      readSmtpConfig({});
    },
    logFailure: () => {},
  });
  expect(await config.json()).toEqual({
    ok: false,
    code: "CONTACT_UNAVAILABLE",
  });
  let delivered = false;
  const limited = await handleContact(request(), {
    getAllowedOrigin: () => origin,
    checkAbuse: async () => false,
    deliver: async () => {
      delivered = true;
    },
    logFailure: () => {},
  });
  expect(limited.status).toBe(429);
  expect(delivered).toBe(false);
});
