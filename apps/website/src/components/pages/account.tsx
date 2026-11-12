"use client";

import { useEffect, useState } from "react";
import { type Dictionary, type Locale } from "@/lib/site";
import { Button } from "@/components/ui/button";
import { useAccountSession } from "@/components/account-session";

export function AccountPage({ t, locale }: { t: Dictionary; locale: Locale }) {
  const { status, error, logout, busy } = useAccountSession();
  const [code, setCode] = useState("");
  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get("error");
    if (value) {
      window.history.replaceState(null, "", window.location.pathname);
      queueMicrotask(() => setCode(value));
    }
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
          {error || code === "ACCOUNT_UNAVAILABLE"
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
          <div className="rounded-2xl border border-border bg-card p-6">
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
          <details className="rounded-2xl border border-border p-6">
            <summary className="cursor-pointer text-lg font-semibold">
              {t.account.connectTitle}
            </summary>
            <p className="mt-4 text-muted-foreground">
              {t.account.connectIntro}
            </p>
            <ol className="mt-5 list-decimal space-y-4 pl-5 text-muted-foreground">
              {t.account.connectSteps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <p className="mt-5 text-sm text-muted-foreground">
              {t.account.connectUnavailable}
            </p>
          </details>
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
