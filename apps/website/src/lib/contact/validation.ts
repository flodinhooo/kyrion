export const reasons = [
  "general",
  "testing",
  "technical",
  "feedback",
  "partnership",
  "other",
] as const;
export const experiences = ["beginner", "intermediate", "advanced"] as const;
export const ecosystems = [
  "homeAssistant",
  "philipsHue",
  "nanoleaf",
  "aqara",
  "matterThread",
  "zigbee",
  "other",
  "none",
] as const;
export type ContactReason = (typeof reasons)[number];
export type Experience = (typeof experiences)[number];
export type Ecosystem = (typeof ecosystems)[number];

export const limits = {
  name: 100,
  email: 254,
  subject: 160,
  message: 5000,
  company: 160,
  country: 100,
} as const;
export type ContactField =
  keyof typeof limits | "reason" | "privacy" | "experience" | "ecosystems";
const fields: readonly ContactField[] = [
  "name",
  "email",
  "subject",
  "message",
  "company",
  "country",
  "reason",
  "privacy",
  "experience",
  "ecosystems",
];
export const validationCodes = [
  "required",
  "invalid",
  "tooLong",
  "email",
  "selection",
  "privacy",
] as const;
export type ValidationCode = (typeof validationCodes)[number];
export type FieldErrors = Partial<Record<ContactField, ValidationCode>>;

export interface ContactPayload {
  name: string;
  email: string;
  subject: string;
  reason: ContactReason;
  message: string;
  company: string;
  privacy: true;
  country: string;
  experience: Experience | "";
  ecosystems: Ecosystem[];
}

type ValidationResult =
  | { ok: true; data: ContactPayload }
  | {
      ok: false;
      code: "CONTACT_INVALID" | "CONTACT_REJECTED";
      fieldErrors: FieldErrors;
    };

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isOneOf<T extends string>(
  value: unknown,
  choices: readonly T[],
): value is T {
  return (
    typeof value === "string" && choices.some((choice) => choice === value)
  );
}

// Intentionally accepts ordinary single mailbox addresses, not display names,
// quoted local parts, address lists or SMTP header syntax.
export function isEmail(value: string): boolean {
  if (value.length > limits.email) return false;
  const parts = value.split("@");
  if (parts.length !== 2) return false;
  const [local, domain] = parts;
  return (
    local.length > 0 &&
    local.length <= 64 &&
    /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$/.test(
      local,
    ) &&
    domain.split(".").length >= 2 &&
    domain
      .split(".")
      .every((label) =>
        /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(label),
      )
  );
}

export function validateContact(input: unknown): ValidationResult {
  const fieldErrors: FieldErrors = {};
  if (!isRecord(input))
    return { ok: false, code: "CONTACT_INVALID", fieldErrors };
  // Do not trim the trap: any supplied content is suspicious. Never mail it.
  if (input.website !== undefined && input.website !== "")
    return { ok: false, code: "CONTACT_REJECTED", fieldErrors };
  const record = input;

  function text(field: keyof typeof limits, required = false) {
    const raw = record[field];
    if (raw === undefined && !required) return "";
    if (typeof raw !== "string") {
      fieldErrors[field] =
        required && raw === undefined ? "required" : "invalid";
      return "";
    }
    const value = raw.normalize("NFC").replace(/\r\n?/g, "\n").trim();
    if (raw.length > limits[field] || value.length > limits[field])
      fieldErrors[field] = "tooLong";
    else if (required && !value) fieldErrors[field] = "required";
    // Message may contain line breaks/tabs, never other control characters.
    else if (
      [...raw].some((char) => {
        const code = char.charCodeAt(0);
        return (
          (code < 32 || code === 127) &&
          !(field === "message" && "\r\n\t".includes(char))
        );
      })
    )
      fieldErrors[field] = "invalid";
    return value;
  }

  const name = text("name", true);
  let email = text("email", true);
  const subject = text("subject", true);
  const message = text("message", true);
  const company = text("company");
  const country = text("country");
  const reason =
    typeof input.reason === "string" ? input.reason.trim() : input.reason;
  if (!isOneOf(reason, reasons))
    fieldErrors.reason =
      reason === "" || reason === undefined ? "required" : "selection";
  if (!fieldErrors.email && !isEmail(email)) fieldErrors.email = "email";
  if (!fieldErrors.email) {
    const [local, domain] = email.split("@");
    email = `${local}@${domain.toLowerCase()}`;
  }
  if (input.privacy !== true) fieldErrors.privacy = "privacy";

  const experience =
    typeof input.experience === "string"
      ? input.experience.trim()
      : (input.experience ?? "");
  if (experience !== "" && !isOneOf(experience, experiences))
    fieldErrors.experience = "selection";
  const selection = input.ecosystems ?? [];
  const selected: Ecosystem[] = [];
  if (!Array.isArray(selection) || selection.length > ecosystems.length)
    fieldErrors.ecosystems = "selection";
  else
    for (const item of selection) {
      if (!isOneOf(item, ecosystems)) fieldErrors.ecosystems = "selection";
      else if (!selected.includes(item)) selected.push(item);
    }
  if (selected.includes("none") && selected.length > 1)
    fieldErrors.ecosystems = "selection";

  if (
    Object.keys(fieldErrors).length ||
    !isOneOf(reason, reasons) ||
    (experience !== "" && !isOneOf(experience, experiences))
  )
    return { ok: false, code: "CONTACT_INVALID", fieldErrors };
  return {
    ok: true,
    data: {
      name,
      email,
      subject,
      reason,
      message,
      company,
      privacy: true,
      // Do not transmit stale testing details after a visitor changes the reason.
      country: reason === "testing" ? country : "",
      experience: reason === "testing" ? experience : "",
      ecosystems: reason === "testing" ? selected : [],
    },
  };
}

export const errorCodes = [
  "CONTACT_INVALID",
  "CONTACT_REJECTED",
  "CONTACT_REQUEST_INVALID",
  "CONTACT_TOO_LARGE",
  "CONTACT_UNAVAILABLE",
  "CONTACT_DELIVERY_FAILED",
  "CONTACT_RATE_LIMITED",
] as const;
export type ContactErrorCode = (typeof errorCodes)[number];
export type ContactResponse =
  | { ok: true; code: "CONTACT_SENT" }
  | { ok: false; code: ContactErrorCode; fieldErrors?: FieldErrors };

export function parseContactResponse(value: unknown): ContactResponse | null {
  if (!isRecord(value)) return null;
  if (value.ok === true && value.code === "CONTACT_SENT")
    return { ok: true, code: "CONTACT_SENT" };
  if (value.ok !== false || !isOneOf(value.code, errorCodes)) return null;
  const fieldErrors: FieldErrors = {};
  if (isRecord(value.fieldErrors)) {
    for (const field of fields) {
      const code = value.fieldErrors[field];
      if (isOneOf(code, validationCodes)) {
        fieldErrors[field] = code;
      }
    }
  }
  return { ok: false, code: value.code, fieldErrors };
}
