export function normalizedLinkCode(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 32) return null;
  const code = value.trim().toUpperCase().replace(/[ -]/g, "");
  return /^[A-Z0-9]{8}$/.test(code)
    ? `${code.slice(0, 4)}-${code.slice(4)}`
    : null;
}

export function deviceVerificationUrl(
  issuer: URL,
  code: string,
  locale: "de" | "en",
) {
  const normalized = normalizedLinkCode(code);
  if (!normalized) throw new Error("Invalid link code");
  const target = new URL(`${issuer.href.replace(/\/$/, "")}/device`);
  target.searchParams.set("user_code", normalized);
  target.searchParams.set("ui_locales", locale);
  return target;
}
