import { randomUUID } from "node:crypto";
import { ContactConfigurationError } from "./config";
import {
  isRecord,
  validateContact,
  type ContactPayload,
  type ContactResponse,
} from "./validation";

export const MAX_BODY_BYTES = 32768;
type FailureCategory =
  | "configuration"
  | "authentication"
  | "connection"
  | "timeout"
  | "rejected"
  | "unknown";
type FailureEvent = {
  event: "contact_delivery_failed";
  requestId: string;
  category: FailureCategory;
};

export interface ContactDependencies {
  getAllowedOrigin: () => string;
  deliver: (data: ContactPayload, requestId: string) => Promise<void>;
  logFailure: (event: FailureEvent) => void;
  // Extension point for a distributed limiter or server-verified challenge.
  checkAbuse?: (request: Request, data: ContactPayload) => Promise<boolean>;
}

function respond(body: ContactResponse, status: number) {
  return Response.json(body, {
    status,
    headers: {
      "Cache-Control": "no-store",
      "X-Content-Type-Options": "nosniff",
    },
  });
}

function category(error: unknown): FailureCategory {
  if (error instanceof ContactConfigurationError) return "configuration";
  const code = isRecord(error) ? error.code : undefined;
  if (code === "EAUTH") return "authentication";
  if (code === "ETIMEDOUT") return "timeout";
  if (code === "ECONNECTION" || code === "ESOCKET" || code === "EDNS")
    return "connection";
  if (code === "EENVELOPE" || code === "EMESSAGE") return "rejected";
  return "unknown";
}

class BodyTooLarge extends Error {}

function deliveryFailure(
  error: unknown,
  dependencies: ContactDependencies,
  requestId: string,
) {
  const failure = category(error);
  dependencies.logFailure({
    event: "contact_delivery_failed",
    requestId,
    category: failure,
  });
  return respond(
    {
      ok: false,
      code:
        failure === "configuration"
          ? "CONTACT_UNAVAILABLE"
          : "CONTACT_DELIVERY_FAILED",
    },
    503,
  );
}

async function readBoundedJson(request: Request): Promise<unknown> {
  const declared = request.headers.get("content-length");
  if (declared && Number(declared) > MAX_BODY_BYTES) throw new BodyTooLarge();
  if (!request.body) throw new SyntaxError();
  const reader = request.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let bytes = 0;
  let body = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > MAX_BODY_BYTES) {
        await reader.cancel();
        throw new BodyTooLarge();
      }
      body += decoder.decode(value, { stream: true });
    }
    body += decoder.decode();
    return JSON.parse(body);
  } finally {
    reader.releaseLock();
  }
}

export async function handleContact(
  request: Request,
  dependencies: ContactDependencies,
): Promise<Response> {
  if (request.method !== "POST")
    return respond({ ok: false, code: "CONTACT_REQUEST_INVALID" }, 405);
  const requestId = randomUUID();
  let allowedOrigin: string;
  try {
    allowedOrigin = dependencies.getAllowedOrigin();
  } catch (error) {
    return deliveryFailure(error, dependencies, requestId);
  }
  // A configured origin works behind proxies without trusting request host headers.
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");
  if (
    !origin ||
    origin !== allowedOrigin ||
    (fetchSite && fetchSite !== "same-origin")
  )
    return respond({ ok: false, code: "CONTACT_REJECTED" }, 403);
  if (
    request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !==
    "application/json"
  )
    return respond({ ok: false, code: "CONTACT_REQUEST_INVALID" }, 415);
  let input: unknown;
  try {
    input = await readBoundedJson(request);
  } catch (error) {
    return respond(
      {
        ok: false,
        code:
          error instanceof BodyTooLarge
            ? "CONTACT_TOO_LARGE"
            : "CONTACT_REQUEST_INVALID",
      },
      error instanceof BodyTooLarge ? 413 : 400,
    );
  }
  const validation = validateContact(input);
  if (!validation.ok) return respond(validation, 400);
  try {
    if (
      dependencies.checkAbuse &&
      !(await dependencies.checkAbuse(request, validation.data))
    )
      return respond({ ok: false, code: "CONTACT_RATE_LIMITED" }, 429);
    await dependencies.deliver(validation.data, requestId);
    return respond({ ok: true, code: "CONTACT_SENT" }, 200);
  } catch (error) {
    return deliveryFailure(error, dependencies, requestId);
  }
}
