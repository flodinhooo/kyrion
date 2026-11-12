import {
  createCipheriv,
  createDecipheriv,
  hkdfSync,
  randomBytes,
} from "node:crypto";

function key(clientSecret: string) {
  return Buffer.from(
    hkdfSync("sha256", clientSecret, "", "kyrion-website-refresh-v1", 32),
  );
}

export function protectRefresh(
  token: string,
  clientSecret: string,
  sessionHash: string,
) {
  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key(clientSecret), iv);
  cipher.setAAD(Buffer.from(sessionHash));
  const encrypted = Buffer.concat([
    cipher.update(token, "utf8"),
    cipher.final(),
  ]);
  return [
    "v1",
    iv.toString("base64url"),
    cipher.getAuthTag().toString("base64url"),
    encrypted.toString("base64url"),
  ].join(".");
}

export function readRefresh(
  value: string,
  clientSecret: string,
  sessionHash: string,
) {
  const parts = value.split(".");
  if (parts.length !== 4 || parts[0] !== "v1")
    throw new Error("Invalid protected credential");
  const iv = Buffer.from(parts[1], "base64url");
  const tag = Buffer.from(parts[2], "base64url");
  if (iv.length !== 12 || tag.length !== 16)
    throw new Error("Invalid protected credential");
  const cipher = createDecipheriv("aes-256-gcm", key(clientSecret), iv);
  cipher.setAAD(Buffer.from(sessionHash));
  cipher.setAuthTag(tag);
  return Buffer.concat([
    cipher.update(Buffer.from(parts[3], "base64url")),
    cipher.final(),
  ]).toString("utf8");
}
