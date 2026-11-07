// Starts only this checkout's Core against the isolated acceptance database.
import { readFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { randomBytes } from "node:crypto";
import { spawn } from "node:child_process";
import { Client } from "pg";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../..",
);
const privateDir = path.join(root, ".run/stabilization");
mkdirSync(privateDir, { recursive: true });
const envFile = path.join(privateDir, "identity-acceptance.env");
if (process.argv.includes("--init")) {
  if (!existsSync(envFile)) {
    const names = [
      "IDENTITY_DB_PASSWORD",
      "IDENTITY_ADMIN_PASSWORD",
      "WEBSITE_CLIENT_SECRET",
      "WEBSITE_DB_PASSWORD",
      "CORE_DB_PASSWORD",
      "LOCAL_PASSWORD",
    ];
    writeFileSync(
      envFile,
      names
        .map((name) => `${name}=${randomBytes(32).toString("base64url")}`)
        .join("\n"),
      { mode: 0o600 },
    );
  }
  console.log(
    "Private acceptance configuration available; no credentials printed.",
  );
  process.exit(0);
}
const settings = Object.fromEntries(
  readFileSync(envFile, "utf8")
    .split(/\r?\n/)
    .filter(Boolean)
    .map((line) => {
      const index = line.indexOf("=");
      return [line.slice(0, index), line.slice(index + 1)];
    }),
);
const secretFile = (name, encoded) => {
  const target = path.join(privateDir, name);
  if (!existsSync(target))
    writeFileSync(
      target,
      encoded ? randomBytes(32).toString("base64url") : randomBytes(32),
      { mode: 0o600 },
    );
  return target;
};
// Renew only this test fixture's setup proof, never installation initialization.
const bootstrap = path.join(privateDir, "identity-bootstrap.secret");
writeFileSync(bootstrap, randomBytes(32).toString("base64url"), {
  mode: 0o600,
});
if (!process.env.JAVA_HOME)
  throw new Error("Set JAVA_HOME to Java 21 before isolated acceptance");
let ready = false;
const deadline = Date.now() + 90_000;
while (!ready && Date.now() < deadline) {
  const probe = new Client({
    host: "127.0.0.1",
    port: 15559,
    database: "kyrion_acceptance",
    user: "kyrion_acceptance",
    password: settings.CORE_DB_PASSWORD,
    connectionTimeoutMillis: 2000,
  });
  try {
    await probe.connect();
    await probe.query("SELECT 1");
    ready = true;
  } catch {
    await new Promise((resolve) => setTimeout(resolve, 500));
  } finally {
    await probe.end().catch(() => {});
  }
}
if (!ready) throw new Error("Isolated Core PostgreSQL did not become ready");
// Container start is not provider readiness: cold schema import can take over a
// minute. Do not let browser account tests race the disposable provider startup.
const issuer = "http://localhost:18089/realms/kyrion";
const providerDeadline = Date.now() + 120_000;
let providerReady = false;
while (!providerReady && Date.now() < providerDeadline) {
  try {
    const response = await fetch(`${issuer}/.well-known/openid-configuration`, {
      signal: AbortSignal.timeout(2000),
    });
    if (response.ok) {
      const value = await response.json();
      providerReady = value.issuer === issuer;
    }
  } catch {
    // This wait targets only the disposable localhost provider, never production.
  }
  if (!providerReady) await new Promise((resolve) => setTimeout(resolve, 500));
}
if (!providerReady)
  throw new Error("Isolated identity provider did not become ready");
const child = spawn(
  path.join(
    process.env.JAVA_HOME,
    "bin",
    process.platform === "win32" ? "java.exe" : "java",
  ),
  [
    "-jar",
    "build/libs/kyrion-core-0.1.0-SNAPSHOT.jar",
    // Do not import the personal installation's infrastructure/.env into tests.
    "--spring.config.import=",
  ],
  {
    cwd: path.join(root, "services/core"),
    stdio: "inherit",
    env: {
      ...process.env,
      SERVER_PORT: "18092",
      KYRION_CORE_ADDRESS: "127.0.0.1",
      KYRION_DATABASE_URL:
        "jdbc:postgresql://127.0.0.1:15559/kyrion_acceptance",
      KYRION_DATABASE_USER: "kyrion_acceptance",
      KYRION_DATABASE_PASSWORD: settings.CORE_DB_PASSWORD,
      KYRION_BOOTSTRAP_SECRET_FILE: bootstrap,
      KYRION_CREDENTIAL_KEY_FILE: secretFile("identity-credential.key", false),
      KYRION_AUDIT_INTEGRITY_KEY_FILE: secretFile("identity-audit.key", false),
      KYRION_KNOWLEDGE_ROOT: path.join(privateDir, "identity-knowledge"),
      KYRION_AI_BASE_URL: "http://127.0.0.1:18999",
      KYRION_KNOWLEDGE_EMBEDDING_URL: "http://127.0.0.1:18999",
      KYRION_CENTRAL_ENABLED: "true",
      KYRION_CENTRAL_ISSUER: "http://localhost:18089/realms/kyrion",
      KYRION_CENTRAL_CLIENT_ID: "kyrion-local",
      KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP: "true",
      KYRION_KNOWLEDGE_WORKER_ENABLED: "false",
      KYRION_CALENDAR_SYNC_SCHEDULER_ENABLED: "false",
      KYRION_HOME_ASSISTANT_REFRESH_ENABLED: "false",
    },
  },
);
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => child.kill());
child.on("exit", (code) => process.exit(code ?? 0));
