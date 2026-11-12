import "server-only";
import {accountConfig} from "@/lib/account/config";
import {database} from "@/lib/account/store";
import {
  InstallationStore,
  installationReport,
  reportSubject,
  validDirectoryId,
} from "@/lib/account/installations";

export const runtime = "nodejs";
const headers = {
  "Cache-Control": "no-store",
  "Referrer-Policy": "no-referrer",
};
const fail = (code: string, status: number) =>
  Response.json({code}, {status, headers});

async function bounded(request: Request): Promise<unknown> {
  const reader = request.body?.getReader();
  if (!reader) throw new Error();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const part = await reader.read();
      if (part.done) break;
      length += part.value.length;
      if (length > 8192) {
        await reader.cancel();
        throw new Error();
      }
      chunks.push(part.value);
    }
  } finally {
    reader.releaseLock();
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function handle(request: Request) {
  const credential = request.headers
    .get("authorization")
    ?.match(/^Bearer ([A-Za-z0-9_.-]{20,32768})$/)?.[1];
  if (!credential) return fail("UNAUTHENTICATED", 401);
  if (request.headers.get("content-type")?.split(";")[0] !== "application/json")
    return fail("INVALID_REPORT", 415);
  let value: unknown;
  try {
    value = await bounded(request);
  } catch {
    return fail("INVALID_REPORT", 400);
  }
  const body = installationReport(value);
  if (request.method !== "DELETE" && !body) return fail("INVALID_REPORT", 400);
  const id =
    value && typeof value === "object" && "id" in value ? value.id : null;
  if (request.method !== "POST" && !validDirectoryId(id))
    return fail("INVALID_REPORT", 400);
  try {
    const config = accountConfig();
    if (!config) return fail("ACCOUNT_DISABLED", 503);
    const store = new InstallationStore(database(config.databaseUrl));
    if (request.method === "POST") {
      const subject = await reportSubject(config, credential);
      if (!subject) return fail("INVALID_PROOF", 401);
      return Response.json(
        await store.report(config.issuer.href, subject, body!),
        {status: 201, headers},
      );
    }
    const changed =
      request.method === "PUT"
        ? await store.update(id as string, credential, body!)
        : await store.remove(id as string, credential);
    return changed
      ? new Response(null, {status: 204, headers})
      : fail("REPORT_NOT_FOUND", 404);
  } catch {
    return fail("DIRECTORY_UNAVAILABLE", 503);
  }
}

export const POST = handle;
export const PUT = handle;
export const DELETE = handle;
