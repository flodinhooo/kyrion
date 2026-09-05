"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { messages, type Locale } from "@/lib/messages";

export function AuthForm({ setup, locale }: { setup: boolean; locale: Locale }) {
  const t = messages[locale];
  const router = useRouter();
  const [error, setError] = useState<"authInvalidCredentials" | "authSetupCompleted" | "authCoreUnavailable" | "authInvalidInput" | "authNetworkError" | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true); setError(null);
    try {
      const response = await fetch(`/api/auth/${setup ? "setup" : "login"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: data.get("username"), password: data.get("password") }),
        signal: AbortSignal.timeout(15_000),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { code?: string };
        setError(body.code === "UNAUTHENTICATED" ? "authInvalidCredentials" :
          body.code === "SETUP_ALREADY_COMPLETED" ? "authSetupCompleted" :
          body.code === "CORE_UNAVAILABLE" ? "authCoreUnavailable" : "authInvalidInput");
        return;
      }
      router.replace("/"); router.refresh();
    } catch { setError("authNetworkError"); }
    finally { setPending(false); }
  }

  return (
    <form
      action={`/api/auth/${setup ? "setup" : "login"}`}
      className="auth-form"
      method="post"
      onSubmit={submit}
    >
      <label>{t.authUsername}<input name="username" autoComplete="username" minLength={3} maxLength={120} pattern="[A-Za-z0-9._-]+" required /></label>
      <label>{t.authPassword}<input name="password" type="password" autoComplete={setup ? "new-password" : "current-password"} minLength={12} maxLength={200} required /></label>
      {setup && <small>{t.authPasswordHint}</small>}
      {error && <p className="auth-error" role="alert">{t[error]}</p>}
      <button disabled={pending} type="submit">{pending ? t.authPending : setup ? t.authSetup : t.authLogin}</button>
    </form>
  );
}
