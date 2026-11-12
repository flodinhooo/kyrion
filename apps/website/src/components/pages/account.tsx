"use client";

import { useEffect, useState } from "react";
import { type Dictionary, type Locale } from "@/lib/site";
import { Button } from "@/components/ui/button";
import { useAccountSession } from "@/components/account-session";

export function AccountPage({ t, locale }: { t: Dictionary; locale: Locale }) {
  const { status, error, logout, busy } = useAccountSession();
  const [code, setCode] = useState("");
  const [connecting, setConnecting] = useState(false);
  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get("error");
    if (value) {
      window.history.replaceState(
        null,
        "",
        window.location.pathname + window.location.hash,
      );
      queueMicrotask(() => setCode(value));
    }
    const syncTab = () => setConnecting(window.location.hash === "#connect");
    const initial = window.setTimeout(syncTab, 0);
    window.addEventListener("hashchange", syncTab);
    return () => {
      clearTimeout(initial);
      window.removeEventListener("hashchange", syncTab);
    };
  }, []);
  const signedIn = Boolean(status?.session);
  return (
    <section className="mx-auto max-w-3xl px-5 py-16 sm:px-8 sm:py-20">
      <h1 className="text-4xl font-semibold">
        {signedIn ? t.account.menu : t.account.title}
      </h1>
      <p className="mt-4 text-lg text-muted-foreground">
        {signedIn ? t.account.welcome : t.account.description}
      </p>
      {(error || code) && (
        <p role="alert" className="mt-5">
          {code === "CONNECT_CODE_INVALID"
            ? t.account.linkCodeInvalid
            : code === "CONNECT_SIGN_IN_REQUIRED"
              ? t.account.linkSignIn
              : error || code === "ACCOUNT_UNAVAILABLE"
                ? t.account.unavailable
                : code === "ACCOUNT_CANCELLED"
                  ? t.account.cancelled
                  : t.account.failed}
        </p>
      )}
      {!status && !error && (
        <p role="status" className="mt-6">
          {t.account.checking}
        </p>
      )}
      {status?.enabled === false && (
        <p className="mt-6">{t.account.disabled}</p>
      )}
      {signedIn ? (
        <div className="mt-8 space-y-6">
          <nav
            aria-label={t.account.accountNavigation}
            className="flex flex-wrap gap-2 rounded-xl border border-border p-2"
          >
            <a
              href="#overview"
              onClick={() => setConnecting(false)}
              aria-current={!connecting ? "page" : undefined}
              className="rounded-lg px-4 py-3 text-sm font-medium hover:bg-muted aria-[current=page]:bg-muted"
            >
              {t.account.overview}
            </a>
            <a
              href="#connect"
              onClick={() => setConnecting(true)}
              aria-current={connecting ? "page" : undefined}
              className="rounded-lg px-4 py-3 text-sm font-medium hover:bg-muted aria-[current=page]:bg-muted"
            >
              {t.account.linkTab}
            </a>
          </nav>
          <div
            hidden={connecting}
            id="overview"
            className="rounded-2xl border border-border bg-card p-6"
          >
            <h2 className="text-xl font-semibold">{t.account.manage}</h2>
            <p className="mt-3 text-muted-foreground">{t.account.manageHelp}</p>
            <form action="/api/account/manage" method="get">
              <button
                type="submit"
                className="mt-4 inline-flex min-h-11 items-center font-medium text-primary underline underline-offset-4"
              >
                {t.account.openSettings}
              </button>
            </form>
          </div>
          <section
            hidden={!connecting}
            id="connect"
            className="rounded-2xl border border-border bg-card p-6 sm:p-8"
          >
            <h2 className="text-2xl font-semibold">{t.account.linkTitle}</h2>
            <p className="mt-3 text-muted-foreground">{t.account.linkHelp}</p>
            <form
              action="/api/account/connect"
              method="post"
              className="mt-6 space-y-4"
            >
              <input type="hidden" name="locale" value={locale} />
              <input
                type="hidden"
                name="csrf"
                value={status?.session?.csrf ?? ""}
              />
              <label htmlFor="installation-code" className="block font-medium">
                {t.account.linkCodeLabel}
              </label>
              <input
                id="installation-code"
                name="userCode"
                placeholder="ABCD-EFGH"
                autoComplete="one-time-code"
                spellCheck={false}
                autoCapitalize="characters"
                minLength={8}
                maxLength={12}
                required
                aria-describedby="installation-code-hint"
                className="min-h-14 w-full rounded-xl border border-border bg-background px-4 py-3 font-mono text-2xl tracking-widest uppercase"
              />
              <p
                id="installation-code-hint"
                className="text-sm text-muted-foreground"
              >
                {t.account.linkHint}
              </p>
              <Button type="submit">{t.account.linkSubmit}</Button>
            </form>
            <p className="mt-5 text-sm text-muted-foreground">
              {t.account.linkOutcome}
            </p>
          </section>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => void logout()}
          >
            {t.account.logout}
          </Button>
        </div>
      ) : status?.enabled ? (
        <div className="mt-8 rounded-2xl border border-border bg-card p-6 sm:p-8">
          <h2 className="text-xl font-semibold">{t.account.startTitle}</h2>
          <p className="mt-3 text-muted-foreground">{t.account.startHelp}</p>
          <div className="mt-6 flex flex-wrap gap-3">
            <form action="/api/account/register" method="post">
              <input type="hidden" name="locale" value={locale} />
              <Button type="submit">{t.account.register}</Button>
            </form>
            <form action="/api/account/login" method="post">
              <input type="hidden" name="locale" value={locale} />
              <Button type="submit" variant="outline">
                {t.account.login}
              </Button>
            </form>
          </div>
          <p className="mt-5 text-sm text-muted-foreground">
            {t.account.remembered}
          </p>
        </div>
      ) : null}
    </section>
  );
}
