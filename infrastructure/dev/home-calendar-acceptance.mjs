// Opt-in real Web/Core/PostgreSQL acceptance. Creates only a new synthetic DB.
import { createRequire } from "node:module";
import { createServer as httpServer } from "node:http";
import { createServer } from "node:net";
import { randomBytes, randomUUID, createHash } from "node:crypto";
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  copyFileSync,
  openSync,
  realpathSync,
  readdirSync,
} from "node:fs";
import { spawn, execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const root = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../..",
);
const { values } = parseArgs({
  options: {
    "web-directory": { type: "string" },
    "core-jar": { type: "string" },
    "core-sha256": { type: "string" },
    "java-home": { type: "string" },
  },
});
if (
  !values["web-directory"] ||
  !/^[a-f0-9]{64}$/.test(values["core-sha256"] ?? "") ||
  !(values["java-home"] || process.env.JAVA_HOME)
)
  throw new Error(
    "Required: --web-directory <separate built Web source copy> --core-sha256 <reviewed SHA256> and JAVA_HOME or --java-home",
  );
const git = (...args) =>
  execFileSync(
    "git",
    ["-c", `safe.directory=${root.replaceAll("\\", "/")}`, ...args],
    { cwd: root, encoding: "utf8", windowsHide: true },
  ).trim();
const sourceCommit = git("rev-parse", "HEAD");
const sourceDirty = git("status", "--porcelain") !== "";
const webSources = createHash("sha256");
const trackedWeb = git(
  "ls-files",
  "apps/web/src",
  "apps/web/public",
  "apps/web/next.config.ts",
  "apps/web/pnpm-lock.yaml",
).split("\n");
const webDirectory = path.resolve(values["web-directory"]);
if (realpathSync(webDirectory) === realpathSync(path.join(root, "apps/web")))
  throw new Error(
    "Use a separate Web source copy; never the personal build directory",
  );
if (
  readdirSync(webDirectory).some(
    (name) => name.startsWith(".env") && name !== ".env.example",
  )
)
  throw new Error(
    "Separate Web source copy must not contain private environment files",
  );
for (const name of trackedWeb) {
  const relative = path.relative(
    path.join(root, "apps/web"),
    path.join(root, name),
  );
  const normalize = (buffer) =>
    /\.(tsx?|css|json|mjs|svg|txt|md|ya?ml)$/.test(name)
      ? Buffer.from(buffer.toString("utf8").replaceAll("\r\n", "\n"))
      : buffer;
  const actual = normalize(readFileSync(path.join(webDirectory, relative)));
  const expected = normalize(readFileSync(path.join(root, name)));
  if (!actual.equals(expected))
    throw new Error(`Separate Web source differs: ${name}`);
  webSources.update(name).update(expected);
}
const webSourceSha256 = webSources.digest("hex");

const require = createRequire(path.join(root, "apps/website/package.json"));
const { Client } = require("pg");
const run = path.join(
  root,
  ".run/private-evidence",
  `ky001-${randomUUID().slice(0, 8)}`,
);
mkdirSync(path.dirname(run), { recursive: true });
mkdirSync(run);
const name = `kyrion-ky001-${randomUUID().slice(0, 8)}`;
const database = "ky001_synthetic";
const password = randomBytes(32).toString("base64url");
const accountPassword = randomBytes(32).toString("base64url");
const bootstrap = randomBytes(32).toString("base64url");
const webDir = webDirectory;
const javaHome = path.resolve(values["java-home"] || process.env.JAVA_HOME);
const jarSource = path.resolve(
  values["core-jar"] ||
    path.join(root, "services/core/build/libs/kyrion-core-0.1.0-SNAPSHOT.jar"),
);
const sha = createHash("sha256").update(readFileSync(jarSource)).digest("hex");
if (sha !== values["core-sha256"]) throw new Error("Unreviewed Core artifact");
copyFileSync(jarSource, path.join(run, "core.jar"));
for (const [file, value] of [
  ["bootstrap.secret", bootstrap],
  ["credential.key", randomBytes(32)],
  ["audit.key", randomBytes(32)],
])
  writeFileSync(path.join(run, file), value, { mode: 0o600 });
writeFileSync(
  path.join(run, "postgres.env"),
  `POSTGRES_DB=${database}\nPOSTGRES_USER=ky001\nPOSTGRES_PASSWORD=${password}\n`,
  { mode: 0o600 },
);

const docker = (...args) =>
  execFileSync("docker", args, { encoding: "utf8", windowsHide: true }).trim();
const dockerEndpoint = JSON.parse(docker("context", "inspect"))[0]?.Endpoints
  ?.docker?.Host;
if (!/^(npipe|unix):/.test(dockerEndpoint ?? ""))
  throw new Error("Local Docker context required");
const postgresImage = docker(
  "image",
  "inspect",
  "postgres:17-alpine",
  "--format",
  "{{.Id}}",
);
const children = [];
let created = false;
let stopping = false;
const attempts = [];
const trap = httpServer((req, res) => {
  attempts.push({ method: req.method, url: req.url });
  res.writeHead(503).end();
});
trap.on("connect", (req, socket) => {
  attempts.push({ method: "CONNECT", url: req.url });
  socket.end("HTTP/1.1 403 Forbidden\r\n\r\n");
});
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const port = () =>
  new Promise((resolve) => {
    const s = createServer();
    s.listen(0, "127.0.0.1", () => {
      const p = s.address().port;
      s.close(() => resolve(p));
    });
  });
const safeEnv = Object.fromEntries(
  Object.entries(process.env).filter(([k]) =>
    /^(PATH|SYSTEMROOT|WINDIR|COMSPEC|TEMP|TMP|USERPROFILE|LOCALAPPDATA|APPDATA|PATHEXT|PROCESSOR_ARCHITECTURE)$/i.test(
      k,
    ),
  ),
);
async function stop(code = 0) {
  if (code !== 0) process.exitCode = code;
  if (stopping) return;
  stopping = true;
  for (const child of children.reverse()) {
    child.kill();
    await delay(200);
  }
  trap.close();
  writeFileSync(
    path.join(run, "external-attempts.json"),
    JSON.stringify(attempts, null, 2),
  );
  if (created) docker("stop", name);
  console.log(`Fixture stopped; synthetic evidence retained in ${run}`);
  process.exit(code);
}
process.on("SIGINT", () => stop(130));
process.on("SIGTERM", () => stop(143));
const waitFor = async (url, child) => {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null)
      throw new Error(
        `Owned process exited before readiness: ${child.exitCode}`,
      );
    try {
      if ((await fetch(url, { signal: AbortSignal.timeout(1500) })).ok) return;
    } catch {}
    await delay(500);
  }
  throw new Error(`Fixture readiness timeout: ${url}`);
};
try {
  docker(
    "run",
    "-d",
    "--rm",
    "--name",
    name,
    "--label",
    "kyrion.test=ky001",
    "--env-file",
    path.join(run, "postgres.env"),
    "--tmpfs",
    "/var/lib/postgresql/data:rw",
    "-p",
    "127.0.0.1::5432",
    postgresImage,
  );
  created = true;
  const dbPort = Number(docker("port", name, "5432/tcp").split(":").at(-1));
  const corePort = await port();
  const webPort = await port();
  await new Promise((resolve) => trap.listen(0, "127.0.0.1", resolve));
  const proxyPort = trap.address().port;
  const db = new Client({
    host: "127.0.0.1",
    port: dbPort,
    database,
    user: "ky001",
    password,
  });
  for (let i = 0; i < 60; i++) {
    try {
      if (
        docker(
          "exec",
          name,
          "pg_isready",
          "-U",
          "ky001",
          "-d",
          database,
        ).includes("accepting connections")
      )
        break;
    } catch {}
    await delay(500);
  }
  const core = spawn(
    path.join(
      javaHome,
      "bin",
      process.platform === "win32" ? "java.exe" : "java",
    ),
    [
      `-Dhttp.proxyHost=127.0.0.1`,
      `-Dhttp.proxyPort=${proxyPort}`,
      "-Dhttps.proxyHost=127.0.0.1",
      `-Dhttps.proxyPort=${proxyPort}`,
      "-Dhttp.nonProxyHosts=localhost|127.*",
      "-jar",
      path.join(run, "core.jar"),
      `--server.port=${corePort}`,
      "--spring.config.import=",
    ],
    {
      cwd: run,
      windowsHide: true,
      stdio: [
        "ignore",
        openSync(path.join(run, "core.log"), "w"),
        openSync(path.join(run, "core-error.log"), "w"),
      ],
      env: {
        ...safeEnv,
        JAVA_HOME: javaHome,
        KYRION_CORE_ADDRESS: "127.0.0.1",
        KYRION_DATABASE_URL: `jdbc:postgresql://127.0.0.1:${dbPort}/${database}`,
        KYRION_DATABASE_USER: "ky001",
        KYRION_DATABASE_PASSWORD: password,
        KYRION_BOOTSTRAP_SECRET_FILE: path.join(run, "bootstrap.secret"),
        KYRION_CREDENTIAL_KEY_FILE: path.join(run, "credential.key"),
        KYRION_AUDIT_INTEGRITY_KEY_FILE: path.join(run, "audit.key"),
        KYRION_KNOWLEDGE_ROOT: path.join(run, "knowledge"),
        KYRION_AI_BASE_URL: "http://127.0.0.1:9",
        KYRION_KNOWLEDGE_EMBEDDING_URL: "http://127.0.0.1:9",
        KYRION_CENTRAL_ENABLED: "false",
        KYRION_KNOWLEDGE_WORKER_ENABLED: "false",
        KYRION_CALENDAR_SYNC_SCHEDULER_ENABLED: "false",
        KYRION_HOME_ASSISTANT_REFRESH_ENABLED: "false",
        KYRION_GOOGLE_CLIENT_ID: "",
        KYRION_GOOGLE_CLIENT_SECRET: "",
        KYRION_GOOGLE_REDIRECT_URI: "",
        KYRION_SPOTIFY_CLIENT_ID: "",
        KYRION_SPOTIFY_CLIENT_SECRET: "",
      },
    },
  );
  children.push(core);
  const coreUrl = `http://127.0.0.1:${corePort}`;
  await waitFor(`${coreUrl}/actuator/health`, core);
  const setup = await fetch(`${coreUrl}/v1/auth/setup`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-kyrion-setup-secret": bootstrap,
    },
    body: JSON.stringify({
      username: "ky001-owner",
      password: accountPassword,
      spaceType: "HOME",
      spaceName: "KY001 Synthetic HOME",
    }),
  });
  if (setup.status !== 201)
    throw new Error(`Synthetic setup failed: ${setup.status}`);
  const owner = (await setup.json()).user.id;
  await db.connect();
  const calendarRole = randomUUID();
  const deniedRole = randomUUID();
  await db.query(
    "INSERT INTO rbac_role(id,installation_owner_id,role_key,display_name) VALUES($1,$2,$3,$4),($5,$2,$6,$7)",
    [
      calendarRole,
      owner,
      "KY001_CALENDAR",
      "Synthetic calendar member",
      deniedRole,
      "KY001_DENIED",
      "Synthetic no-calendar role",
    ],
  );
  await db.query(
    "INSERT INTO rbac_role_permission(role_id,permission_key) SELECT $1,permission_key FROM rbac_permission WHERE permission_key=ANY($2)",
    [
      calendarRole,
      [
        "calendar:read",
        "calendar:create",
        "calendar:update",
        "calendar:delete",
      ],
    ],
  );
  const users = { owner };
  for (const [key, role] of [
    ["partner", calendarRole],
    ["observer", calendarRole],
    ["denied", deniedRole],
  ]) {
    const id = randomUUID();
    users[key] = id;
    await db.query(
      "INSERT INTO user_account(id,username,password_hash,workspace_owner_id) SELECT $1,$2,password_hash,$3 FROM user_account WHERE id=$3",
      [id, `ky001-${key}`, owner],
    );
    await db.query(
      "INSERT INTO rbac_user_role(user_id,role_id) VALUES($1,$2)",
      [id, role],
    );
  }
  const version = (
    await db.query(
      "SELECT version FROM flyway_schema_history WHERE success ORDER BY installed_rank DESC LIMIT 1",
    )
  ).rows[0].version;
  const postgresVersion = (await db.query("SHOW server_version")).rows[0]
    .server_version;
  await db.end();
  const web = spawn(
    process.execPath,
    [
      path.join(webDir, "node_modules/next/dist/bin/next"),
      "start",
      "--port",
      String(webPort),
      "--hostname",
      "127.0.0.1",
    ],
    {
      cwd: webDir,
      windowsHide: true,
      env: {
        ...safeEnv,
        CORE_SERVICE_URL: coreUrl,
        NEXT_TELEMETRY_DISABLED: "1",
      },
      stdio: [
        "ignore",
        openSync(path.join(run, "web.log"), "w"),
        openSync(path.join(run, "web-error.log"), "w"),
      ],
    },
  );
  children.push(web);
  const webUrl = `http://127.0.0.1:${webPort}`;
  await waitFor(`${webUrl}/login`, web);
  writeFileSync(
    path.join(run, "runtime.json"),
    JSON.stringify({
      run,
      name,
      coreUrl,
      webUrl,
      corePid: core.pid,
      webPid: web.pid,
      dbPort,
      database,
      password,
      accountPassword,
      users,
      version,
      sourceCommit,
      sourceDirty,
      webSourceSha256,
      postgresImage,
      postgresVersion,
      coreSha256: sha,
      webDir,
    }),
    { mode: 0o600 },
  );
  console.log(
    JSON.stringify({
      ready: true,
      run,
      coreUrl,
      webUrl,
      schema: version,
      container: name,
      corePid: core.pid,
      webPid: web.pid,
    }),
  );
  const browser = spawn(
    process.execPath,
    [
      path.join(root, "infrastructure/dev/home-calendar-browser-checks.mjs"),
      path.join(run, "runtime.json"),
    ],
    { cwd: root, windowsHide: true, stdio: "inherit", env: safeEnv },
  );
  children.push(browser);
  const timeout = setTimeout(() => {
    console.error("Acceptance exceeded 15 minutes");
    void stop(1);
  }, 15 * 60_000);
  const code = await new Promise((resolve, reject) => {
    browser.on("error", reject);
    browser.on("exit", (value) => resolve(value ?? 1));
  });
  clearTimeout(timeout);
  if (attempts.length) {
    console.error("Unexpected outbound HTTP(S) attempts were blocked");
    await stop(1);
  }
  await stop(code);
} catch (error) {
  console.error(error.message);
  await stop(1);
}
