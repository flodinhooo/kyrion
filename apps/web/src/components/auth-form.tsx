"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { messages, type Locale } from "@/lib/messages";

export function AuthForm({ setup, locale, registration = false }: { setup: boolean; locale: Locale; registration?: boolean }) {
  const t = messages[locale];
  const router = useRouter();
  const [error, setError] = useState<"authInvalidCredentials" | "authSetupCompleted" | "authCoreUnavailable" | "authInvalidInput" | "authNetworkError" | "authPasswordMismatch" | "authUsernameTaken" | "authInvitationInvalid" | null>(null);
  const [pending, setPending] = useState(false);
  const creatingAccount = setup || registration;
  const endpoint = `/api/auth/${setup ? "setup" : registration ? "register" : "login"}`;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (pending) return;
    if (creatingAccount && data.get("password") !== data.get("passwordConfirmation")) {
      setError("authPasswordMismatch");
      return;
    }
    setPending(true); setError(null);
    try {
      const response = await fetch(endpoint, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: data.get("username"), password: data.get("password"),
          ...(registration && !setup ? { invitationCode: data.get("invitationCode") } : {}) }),
        signal: AbortSignal.timeout(15_000),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { code?: string };
        setError(body.code === "USERNAME_TAKEN" ? "authUsernameTaken" :
          body.code === "INVITATION_INVALID" ? "authInvitationInvalid" :
          body.code === "UNAUTHENTICATED" ? "authInvalidCredentials" :
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
      action={endpoint}
      className="auth-form"
      method="post"
      onSubmit={submit}
    >
      <label>{t.authUsername}<input name="username" autoComplete="username" minLength={3} maxLength={120} pattern="[A-Za-z0-9._-]+" required /></label>
      <label>{t.authPassword}<input name="password" type="password" autoComplete={creatingAccount ? "new-password" : "current-password"} minLength={12} maxLength={200} required /></label>
      {creatingAccount && <>
        <small id="password-hint">{setup ? t.authPasswordHint : t.authRegistrationPasswordHint}</small>
        <label>{t.authConfirmPassword}<input name="passwordConfirmation" type="password" autoComplete="new-password" minLength={12} maxLength={200} aria-describedby="password-hint" required /></label>
      </>}
      {registration && !setup && <label>{t.authInvitationCode}<input name="invitationCode" autoComplete="off" autoCapitalize="none" spellCheck={false} minLength={43} maxLength={43} pattern="[A-Za-z0-9_-]{43}" required /></label>}
      {error && <p className="auth-error" role="alert">{t[error]}</p>}
      <button disabled={pending} type="submit">{pending ? t.authPending : setup ? t.authSetup : registration ? t.authSignupTitle : t.authLogin}</button>
    </form>
  );
}
