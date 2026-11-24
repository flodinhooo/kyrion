import type { RemovalAudit } from "@/lib/account/store";
import {
  credentialId,
  fetchInventory,
} from "@/lib/account/credential-inventory";
import { isAccountAction } from "@/lib/account/actions";
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
        new URL(
          `${request.nextUrl.searchParams.get("locale") === "en" ? "/en" : ""}/account#settings`,
          config.origin,
        ),
        303,
      ),
    );
  const store = new AccountStore(database(config.databaseUrl), config);
  try {
    if (operation === "methods") {
      const inventory = await store.credentialInventory(
        request.cookies.get(sessionCookie)?.value ?? "",
      );
      return protect(
        NextResponse.json(
          inventory ? { inventory } : { code: "UNAUTHENTICATED" },
          { status: inventory ? 200 : 401 },
        ),
      );
    }
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
        let removal: RemovalAudit | undefined;
        if (flow.destination === "remove") {
          if (
            !credentialId(flow.credentialId) ||
            !credentialId(flow.removalCorrelation)
          )
            throw Error("Invalid removal audit reference");
          removal = {
            credentialId: flow.credentialId,
            correlationId: flow.removalCorrelation,
            result: "CREDENTIAL_REMOVAL_RETURNED",
          };
          try {
            const inventory = await fetchInventory(
              config,
              identity.accessToken,
            );
            removal.result = inventory.methods.some(
              (method) => method.id === flow.credentialId,
            )
              ? "CREDENTIAL_REMOVAL_RETAINED"
              : "CREDENTIAL_REMOVAL_ABSENT";
          } catch {
            /* Do not discard a valid login if a separate inventory read fails. */
          }
        }
        const session = await store.issue(
          identity.issuer,
          identity.subject,
          identity.expiresAt,
          identity.refreshToken,
          removal,
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
    if (
      operation === "login" ||
      operation === "register" ||
      isAccountAction(operation)
    ) {
      const form = await request.formData();
      const locale = form.get("locale") === "en" ? "en" : "de";
      failureTarget = new URL(
        locale === "en" ? "/en/account" : "/account",
        config.origin,
      );
      let expectedSubject: string | null = null;
      let selectedCredential: string | null = null;
      if (isAccountAction(operation)) {
        const token = request.cookies.get(sessionCookie)?.value ?? "";
        const session = await store.session(token);
        const expected = Buffer.from(session?.csrf ?? "");
        const actual = Buffer.from(String(form.get("csrf") ?? ""));
        if (
          !session ||
          !actual.length ||
          actual.length !== expected.length ||
          !timingSafeEqual(actual, expected)
        )
          return protect(
            NextResponse.json({ code: "CSRF_INVALID" }, { status: 403 }),
          );
        if (operation === "remove") {
          const selected = form.get("credentialId");
          if (!credentialId(selected) || form.get("confirm") !== "yes")
            return protect(
              NextResponse.json(
                { code: "INVALID_REMOVAL_INTENT" },
                { status: 400 },
              ),
            );
          const inventory = await store.credentialInventory(token);
          if (!inventory)
            return protect(
              NextResponse.json({ code: "UNAUTHENTICATED" }, { status: 401 }),
            );
          const method = inventory.methods.find((item) => item.id === selected);
          if (!method?.removable) {
            failureTarget.searchParams.set(
              "error",
              "CREDENTIAL_REMOVAL_BLOCKED",
            );
            return protect(NextResponse.redirect(failureTarget, 303));
          }
          selectedCredential = selected;
        }
        expectedSubject = await store.actionSubject(token);
        if (!expectedSubject)
          return protect(
            NextResponse.json({ code: "UNAUTHENTICATED" }, { status: 401 }),
          );
      }
      const flow = {
        state: secret(),
        nonce: secret(),
        verifier: secret(),
        locale,
        destination: isAccountAction(operation)
          ? operation
          : form.get("destination") === "connect"
            ? "connect"
            : "account",
        expectedSubject,
        credentialId: selectedCredential,
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
