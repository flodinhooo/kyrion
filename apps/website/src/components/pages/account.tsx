"use client";

import { useEffect, useState } from "react";
import type { Dictionary, Locale } from "@/lib/site";
import { Button } from "@/components/ui/button";

type Status = {
  enabled: boolean;
  session?: { id: string; csrf: string; expiresAt: string } | null;
};

function readStatus(value: unknown): Status {
  if (
    typeof value !== "object" ||
    value === null ||
    !("enabled" in value) ||
    typeof value.enabled !== "boolean"
  )
    throw new Error("Invalid account response");
  if (!value.enabled) return { enabled: false };
  if (!("session" in value) || value.session === null)
    return { enabled: true, session: null };
  const session = value.session;
  if (
    typeof session !== "object" ||
    !("id" in session) ||
    typeof session.id !== "string" ||
    !("csrf" in session) ||
    typeof session.csrf !== "string" ||
    !("expiresAt" in session) ||
    typeof session.expiresAt !== "string" ||
    !Number.isFinite(Date.parse(session.expiresAt))
  )
    throw new Error("Invalid account session");
  return {
    enabled: true,
    session: {
      id: session.id,
      csrf: session.csrf,
      expiresAt: session.expiresAt,
    },
  };
}
export function AccountPage({ t, locale }: { t: Dictionary; locale: Locale }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const code = new URLSearchParams(window.location.search).get("error");
    if (code) window.history.replaceState(null, "", window.location.pathname);
    fetch("/api/account/session", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error();
        const data = readStatus(await response.json());
        if (active) {
          setStatus(data);
          if (code)
            setError(
              code === "ACCOUNT_UNAVAILABLE"
                ? t.account.unavailable
                : code === "ACCOUNT_CANCELLED"
                  ? t.account.cancelled
                  : t.account.failed,
            );
        }
      })
      .catch(() => {
        if (active) setError(t.account.unavailable);
      });
    return () => {
      active = false;
    };
  }, [t]);

  useEffect(() => {
    if (!status?.session) return;
    const timer = window.setTimeout(
      () => setStatus({ enabled: true, session: null }),
      Math.max(0, Date.parse(status.session.expiresAt) - Date.now()),
    );
    return () => window.clearTimeout(timer);
  }, [status]);

  async function logout() {
    try {
      const response = await fetch("/api/account/logout", {
        method: "POST",
        headers: { "x-kyrion-csrf": status?.session?.csrf ?? "" },
      });
      if (response.ok) setStatus({ enabled: true, session: null });
      else setError(t.account.unavailable);
    } catch {
      setError(t.account.unavailable);
    }
  }

  return (
    <section className="mx-auto max-w-3xl px-5 py-20 sm:px-8">
      <h1 className="text-4xl font-semibold">{t.account.title}</h1>
      <p className="mt-5 text-muted-foreground">{t.account.description}</p>
      <p className="mt-5 text-muted-foreground">{t.account.boundary}</p>
      {error && (
        <p role="alert" className="mt-5">
          {error}
        </p>
      )}
      {status?.enabled === false && (
        <p className="mt-5">{t.account.disabled}</p>
      )}
      {status?.session ? (
        <div className="mt-8 space-y-5">
          <p>{t.account.signedIn}</p>
          <p>{t.account.expiry}</p>
          <Button onClick={logout}>{t.account.logout}</Button>
          <p className="text-sm text-muted-foreground">
            {t.account.logoutScope}
          </p>
        </div>
      ) : (
        status?.enabled && (
          <form action="/api/account/login" method="post" className="mt-8">
            <input type="hidden" name="locale" value={locale} />
            <Button type="submit">{t.account.login}</Button>
          </form>
        )
      )}
    </section>
  );
}
