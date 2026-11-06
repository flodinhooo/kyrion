import "server-only";
import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { accountConfig } from "@/lib/account/config";
import { authenticate, authorizationUrl } from "@/lib/account/oidc";
import { AccountStore, database, secret } from "@/lib/account/store";

export const runtime = "nodejs";
const sessionCookie = "kyrion_website_session";
const flowCookie = "kyrion_website_flow";
type Context = { params: Promise<{ operation: string }> };

function protect(response: NextResponse) {
  response.headers.set("Cache-Control", "no-store");
  response.headers.set("Referrer-Policy", "no-referrer");
  return response;
}

export async function GET(request: NextRequest, context: Context) {
  const { operation } = await context.params;
  let config;
  try {
    config = accountConfig();
  } catch {
    return protect(
      NextResponse.json(
        { code: "ACCOUNT_CONFIGURATION_INVALID" },
        { status: 503 },
      ),
    );
  }
  if (!config)
    return protect(NextResponse.json({ enabled: false }, { status: 200 }));
  const store = new AccountStore(database(config.databaseUrl));
  try {
    if (operation === "session") {
      const session = await store.session(
        request.cookies.get(sessionCookie)?.value ?? "",
      );
      return protect(NextResponse.json({ enabled: true, session }));
    }
    if (operation !== "callback")
      return protect(NextResponse.json({ code: "NOT_FOUND" }, { status: 404 }));
    const flow = await store.consume(
      request.cookies.get(flowCookie)?.value ?? "",
    );
    let code = "ACCOUNT_AUTHENTICATION_FAILED";
    if (flow) {
      try {
        const identity = await authenticate(
          config,
          new URL(config.callback + request.nextUrl.search),
          flow,
        );
        const session = await store.issue(
          identity.issuer,
          identity.subject,
          identity.expiresAt,
        );
        const previous = request.cookies.get(sessionCookie)?.value;
        if (previous) await store.revoke(previous);
        const response = NextResponse.redirect(
          new URL(
            flow.locale === "en" ? "/en/account" : "/account",
            config.origin,
          ),
          303,
        );
        response.cookies.set(sessionCookie, session.id, {
          httpOnly: true,
          secure: !config.developmentHttp,
          sameSite: "strict",
          path: "/",
          expires: new Date(session.expiresAt),
        });
        response.cookies.delete(flowCookie);
        return protect(response);
      } catch {
        code =
          request.nextUrl.searchParams.get("error") === "access_denied"
            ? "ACCOUNT_CANCELLED"
            : "ACCOUNT_AUTHENTICATION_FAILED";
      }
    }
    const target = new URL(
      flow?.locale === "en" ? "/en/account" : "/account",
      config.origin,
    );
    target.searchParams.set("error", code);
    const response = NextResponse.redirect(target, 303);
    response.cookies.delete(flowCookie);
    return protect(response);
  } catch {
    if (operation === "callback") {
      const target = new URL("/account", config.origin);
      target.searchParams.set("error", "ACCOUNT_UNAVAILABLE");
      return protect(NextResponse.redirect(target, 303));
    }
    return protect(
      NextResponse.json({ code: "ACCOUNT_UNAVAILABLE" }, { status: 503 }),
    );
  }
}

export async function POST(request: NextRequest, context: Context) {
  const { operation } = await context.params;
  let failureTarget: URL | undefined;
  try {
    const config = accountConfig();
    if (!config)
      return protect(
        NextResponse.json({ code: "ACCOUNT_DISABLED" }, { status: 503 }),
      );
    if (request.headers.get("origin") !== config.origin)
      return protect(
        NextResponse.json({ code: "CSRF_INVALID" }, { status: 403 }),
      );
    const store = new AccountStore(database(config.databaseUrl));
    if (operation === "login") {
      const form = await request.formData();
      const locale = form.get("locale") === "en" ? "en" : "de";
      failureTarget = new URL(
        locale === "en" ? "/en/account" : "/account",
        config.origin,
      );
      const flow = {
        state: secret(),
        nonce: secret(),
        verifier: secret(),
        locale,
      } as const;
      const url = await authorizationUrl(config, flow);
      const id = secret();
      await store.begin(id, flow);
      const response = NextResponse.redirect(url, 303);
      response.cookies.set(flowCookie, id, {
        httpOnly: true,
        secure: !config.developmentHttp,
        sameSite: "lax",
        path: "/",
        maxAge: 300,
      });
      return protect(response);
    }
    if (operation === "logout") {
      const token = request.cookies.get(sessionCookie)?.value ?? "";
      const session = await store.session(token);
      const csrf = request.headers.get("x-kyrion-csrf") ?? "";
      const csrfBytes = Buffer.from(csrf);
      const expectedCsrf = Buffer.from(session?.csrf ?? "");
      if (
        !session ||
        csrfBytes.length !== expectedCsrf.length ||
        !timingSafeEqual(csrfBytes, expectedCsrf)
      )
        return protect(
          NextResponse.json({ code: "CSRF_INVALID" }, { status: 403 }),
        );
      await store.revoke(token);
      const response = NextResponse.json({ ok: true });
      response.cookies.delete(sessionCookie);
      return protect(response);
    }
    return protect(NextResponse.json({ code: "NOT_FOUND" }, { status: 404 }));
  } catch {
    if (failureTarget) {
      failureTarget.searchParams.set("error", "ACCOUNT_UNAVAILABLE");
      return protect(NextResponse.redirect(failureTarget, 303));
    }
    return protect(
      NextResponse.json({ code: "ACCOUNT_UNAVAILABLE" }, { status: 503 }),
    );
  }
}
