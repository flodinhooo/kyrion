import type SMTPTransport from "nodemailer/lib/smtp-transport";
import { isEmail } from "./validation";

export function readContactOrigin(
  env: Readonly<Record<string, string | undefined>>,
): string {
  try {
    const url = new URL(env.CONTACT_FORM_ORIGIN?.trim() ?? "");
    const local =
      url.hostname === "localhost" ||
      url.hostname === "127.0.0.1" ||
      url.hostname === "[::1]";
    if (
      (url.protocol !== "https:" && !(local && url.protocol === "http:")) ||
      url.username ||
      url.password ||
      url.pathname !== "/" ||
      url.search ||
      url.hash
    )
      throw new Error();
    return url.origin;
  } catch {
    throw new ContactConfigurationError();
  }
}

export class ContactConfigurationError extends Error {
  constructor() {
    super("Contact delivery is not configured");
    this.name = "ContactConfigurationError";
  }
}

export function readSmtpConfig(
  env: Readonly<Record<string, string | undefined>>,
) {
  const host = env.SMTP_HOST?.trim();
  const port = env.SMTP_PORT?.trim();
  const user = env.SMTP_USER?.trim();
  const pass = env.SMTP_PASSWORD;
  const from = env.SMTP_FROM?.trim();
  const to = env.CONTACT_EMAIL_TO?.trim();
  if (
    !host ||
    host.length > 253 ||
    !/^[A-Za-z0-9.-]+$/.test(host) ||
    (port !== "465" && port !== "587") ||
    !user ||
    !isEmail(user) ||
    !pass?.trim() ||
    !from ||
    !isEmail(from) ||
    !to ||
    !isEmail(to)
  )
    throw new ContactConfigurationError();
  const transport: SMTPTransport.Options = {
    host,
    port: Number(port),
    secure: port === "465",
    requireTLS: true,
    auth: { user, pass },
    tls: { minVersion: "TLSv1.2", rejectUnauthorized: true },
    connectionTimeout: 5000,
    greetingTimeout: 5000,
    socketTimeout: 15000,
    dnsTimeout: 5000,
    disableFileAccess: true,
    disableUrlAccess: true,
    logger: false,
    debug: false,
  };
  return { transport, from, to };
}
