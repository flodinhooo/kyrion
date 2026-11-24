import type { AccountConfig } from "./config";

export type CredentialMethod = {
  id: string;
  kind: "passkey" | "securityKey" | "otp" | "recovery";
  label: string;
  createdAt: number | null;
  removable: boolean;
};
export type CredentialInventory = {
  methods: CredentialMethod[];
  hasPassword: boolean;
};
export const credentialId = (value: unknown): value is string =>
  typeof value === "string" &&
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value))
    throw Error("Invalid credential metadata");
  return value as Record<string, unknown>;
}

export function parseInventory(value: unknown): CredentialInventory {
  if (!Array.isArray(value) || value.length > 50)
    throw Error("Invalid credential inventory");
  const methods: CredentialMethod[] = [];
  let hasPassword = false;
  const ids = new Set<string>();
  for (const entry of value) {
    const container = object(entry);
    const rows = container.userCredentialMetadatas;
    if (!Array.isArray(rows) || rows.length > 200)
      throw Error("Invalid credential list");
    for (const item of rows) {
      const row = object(object(item).credential);
      if (container.type === "password") {
        if (row.type !== "password" || typeof row.id !== "string" || !row.id)
          throw Error("Invalid password metadata");
        hasPassword = true;
        continue;
      }
      const kind =
        container.type === "webauthn-passwordless"
          ? "passkey"
          : container.type === "webauthn"
            ? "securityKey"
            : container.type === "otp"
              ? "otp"
              : container.type === "recovery-authn-codes"
                ? "recovery"
                : null;
      if (!kind) continue;
      if (row.type !== container.type)
        throw Error("Inconsistent credential type");
      if (!credentialId(row.id) || ids.has(row.id))
        throw Error("Invalid credential identifier");
      ids.add(row.id);
      if (
        row.userLabel != null &&
        (typeof row.userLabel !== "string" || row.userLabel.length > 512)
      )
        throw Error("Invalid credential label");
      methods.push({
        id: row.id,
        kind,
        label: typeof row.userLabel === "string" ? row.userLabel : "",
        createdAt:
          typeof row.createdDate === "number" &&
          Number.isFinite(row.createdDate) &&
          row.createdDate >= 0 &&
          row.createdDate <= 8640000000000000
            ? row.createdDate
            : null,
        removable: container.removeable === true,
      });
    }
  }
  const passkeys = methods.filter((m) => m.kind === "passkey");
  return {
    hasPassword,
    methods: methods.map((m) => ({
      ...m,
      removable:
        m.removable &&
        (hasPassword || (m.kind !== "passkey" && passkeys.length > 0)),
    })),
  };
}

export async function fetchInventory(
  config: AccountConfig,
  accessToken: string,
): Promise<CredentialInventory> {
  const url = new URL(
    config.issuer.href.replace(/\/$/, "") + "/account/credentials",
  );
  const response = await fetch(url, {
    headers: {
      authorization: `Bearer ${accessToken}`,
      accept: "application/json",
    },
    cache: "no-store",
    redirect: "error",
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw Error("Credential inventory unavailable");
  const text = await response.text();
  if (text.length > 256000) throw Error("Credential inventory oversized");
  return parseInventory(JSON.parse(text));
}
