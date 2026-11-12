import "server-only";
import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";
import { accountConfig } from "@/lib/account/config";
import {
  authenticate,
  authorizationUrl,
  revokeRefresh,
} from "@/lib/account/oidc";
import { AccountStore, database, secret } from "@/lib/account/store";
import {
  normalizedLinkCode,
  deviceVerificationUrl,
} from "@/lib/account/device-link";

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
  if (operation === "manage")
    return protect(
      NextResponse.redirect(
        new URL(`${config.issuer.href.replace(/\/$/, "")}/account/`),
        303,
      ),
    );
  const store = new AccountStore(database(config.databaseUrl), config);
  try {
    if (operation === "session") {
      const session = await store.session(
        request.cookies.get(sessionCookie)?.value ?? "",
      );
      const response = protect(NextResponse.json({ enabled: true, session }));
      if (!session && request.cookies.has(sessionCookie))
        response.cookies.delete(sessionCookie);
      return response;
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
          identity.refreshToken,
        );
        const previous = request.cookies.get(sessionCookie)?.value;
        if (previous) await store.revoke(previous);
        const response = NextResponse.redirect(
          new URL(
            `${flow.locale === "en" ? "/en" : ""}/${flow.destination === "connect" ? "connect" : "account"}`,
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
    const store = new AccountStore(database(config.databaseUrl), config);
    if (operation === "connect") {
      const form = await request.formData();
      const locale = form.get("locale") === "en" ? "en" : "de";
      failureTarget = new URL(
        locale === "en" ? "/en/connect" : "/connect",
        config.origin,
      );
      const session = await store.session(
        request.cookies.get(sessionCookie)?.value ?? "",
      );
      if (!session) {
        failureTarget.searchParams.set("error", "CONNECT_SIGN_IN_REQUIRED");
        return protect(NextResponse.redirect(failureTarget, 303));
      }
      const supplied = form.get("csrf");
      const expected = Buffer.from(session.csrf);
      const actual = Buffer.from(typeof supplied === "string" ? supplied : "");
      if (
        expected.length !== actual.length ||
        !timingSafeEqual(expected, actual)
      )
        return protect(
          NextResponse.json({ code: "CSRF_INVALID" }, { status: 403 }),
        );
      const code = normalizedLinkCode(form.get("userCode"));
      if (!code) {
        failureTarget.searchParams.set("error", "CONNECT_CODE_INVALID");
        return protect(NextResponse.redirect(failureTarget, 303));
      }
      return protect(
        NextResponse.redirect(
          deviceVerificationUrl(config.issuer, code, locale),
          303,
        ),
      );
    }
    if (operation === "login" || operation === "register") {
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
        destination: form.get("destination") === "connect" ? "connect" : "account",
      } as const;
      const url = await authorizationUrl(
        config,
        flow,
        operation === "register",
      );
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
      const session = await store.forLogout(token);
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
      const refreshToken = await store.revoke(token);
      if (refreshToken) {
        try {
          await revokeRefresh(config, refreshToken);
        } catch {
          /* Local logout already committed. */
        }
      }
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
