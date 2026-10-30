// Isolated browser fixture. Never connects to a real Core or database.
import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

let initialized = false;
let space = { id: "fixture-space", name: "Kyrion", type: "HOME", status: "ACTIVE", defaultRoleKey: "USER" };
let invitations = [];
const code = "I".repeat(43);
const permissions = ["devices:read", "system_settings:update", "users:read", "roles:read", "invitations:create"];
const user = { id: "fixture-owner", username: "owner", canInvite: true, roles: ["OWNER"], permissions };
const roles = [
  { id: "fixture-user-role", key: "USER", name: "User", system: true, permissions: ["devices:read"], userCount: 0 },
  { id: "fixture-owner-role", key: "OWNER", name: "Owner", system: true, permissions, userCount: 1 },
];

const core = createServer(async (request, response) => {
  response.setHeader("Content-Type", "application/json");
  response.setHeader("Cache-Control", "no-store");
  const reply = (status, body) => { response.statusCode = status; response.end(JSON.stringify(body)); };
  let raw = "";
  for await (const chunk of request) raw += chunk;
  const body = raw ? JSON.parse(raw) : {};
  if (request.url === "/fixture/reset") {
    initialized = false; invitations = []; return reply(200, {});
  }
  if (request.url === "/v1/auth/setup/status") return reply(200, { setupRequired: !initialized });
  if (request.url === "/v1/auth/setup") {
    if (initialized) return reply(409, { code: "SETUP_ALREADY_COMPLETED" });
    if (request.headers["x-kyrion-setup-secret"] !== "S".repeat(43)) return reply(403, { code: "BOOTSTRAP_FORBIDDEN" });
    initialized = true; space = { ...space, type: body.spaceType, name: body.spaceName };
    return reply(201, { user, sessionToken: "fixture-session", expiresAt: "2099-01-01T00:00:00Z" });
  }
  if (request.url === "/v1/auth/register") {
    if (body.invitationCode !== code || !invitations.some((i) => i.status === "ACTIVE")) return reply(400, { code: "INVITATION_INVALID" });
    invitations = invitations.map((i) => ({ ...i, status: "USED", useCount: 1 }));
    return reply(201, { user, sessionToken: "fixture-session", expiresAt: "2099-01-01T00:00:00Z" });
  }
  if (request.headers.authorization !== "Bearer fixture-session") return reply(401, { code: "UNAUTHENTICATED" });
  if (request.url === "/v1/auth/me") return reply(200, { ...user, space });
  if (request.url === "/v1/space") {
    if (request.method === "PUT") space = { ...space, ...body };
    return reply(200, space);
  }
  if (request.url === "/v1/rbac/roles") return reply(200, roles);
  if (request.url === "/v1/rbac/users") return reply(200, [{ ...user, enabled: true }]);
  if (request.url === "/v1/space/invitations") {
    if (request.method === "GET") return reply(200, invitations);
    const invitation = { id: "12345678-1234-1234-1234-123456789012", createdBy: user.id, createdAt: new Date().toISOString(), expiresAt: "2099-01-01T00:00:00Z", roleKey: "USER", maxUses: body.maxUses, useCount: 0, status: "ACTIVE" };
    invitations.push(invitation);
    return reply(201, { ...invitation, code });
  }
  if (request.url?.startsWith("/v1/space/invitations/") && request.method === "DELETE") {
    invitations = invitations.map((i) => ({ ...i, status: "REVOKED" }));
    response.statusCode = 204; return response.end();
  }
  return reply(200, []);
});

core.listen(33081, "127.0.0.1", () => {
  const webDirectory = fileURLToPath(new URL("../apps/web/", import.meta.url));
  const next = fileURLToPath(new URL("../apps/web/node_modules/next/dist/bin/next", import.meta.url));
  const child = spawn(process.execPath, [next, "start", "--hostname", "127.0.0.1", "--port", "3102"], {
    cwd: webDirectory, stdio: "inherit", windowsHide: true,
    env: { ...process.env, CORE_SERVICE_URL: "http://127.0.0.1:33081", KYRION_INSECURE_LAN_HTTP: "true" },
  });
  const stop = () => { child.kill(); core.close(); };
  process.on("SIGINT", stop); process.on("SIGTERM", stop);
  child.on("exit", (status) => { core.close(); process.exitCode = status ?? 1; });
});
