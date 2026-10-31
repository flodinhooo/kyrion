"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { messages, type Locale } from "@/lib/messages";

import { identityMessages } from "@/features/spaces/identity-messages";
import { spaceMessages } from "@/features/spaces/messages";

export function AuthForm({ setup, locale, registration = false }: { setup: boolean; locale: Locale; registration?: boolean }) {
  const t = messages[locale];
  const st = spaceMessages[locale];
  const it = identityMessages[locale];
  const [verificationSent, setVerificationSent] = useState(false);
  const invitationInput = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!registration) return;
    const code = new URLSearchParams(window.location.hash.slice(1)).get("invitation");
    if (code && /^[A-Za-z0-9_-]{43}$/.test(code)) {
      if (invitationInput.current) invitationInput.current.value = code;
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, [registration]);
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
          ...(setup ? { setupSecret: data.get("setupSecret"), spaceName: data.get("spaceName"), spaceType: data.get("spaceType") } : {}),
          ...(registration && !setup ? { invitationCode: data.get("invitationCode"), ...(data.get("email") ? { email: data.get("email"), emailProof: data.get("emailProof") } : {}) } : {}) }),
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
      {setup && <>
        <label>{st.name}<input name="spaceName" minLength={1} maxLength={120} required /></label>
        <label>{st.type}<select name="spaceType" defaultValue="HOME"><option value="HOME">{st.home}</option><option value="BUSINESS">{st.business}</option></select></label>
      </>}
      {setup && <label>{t.authSetupSecret}<input name="setupSecret" type="password" autoComplete="off" minLength={43} maxLength={43} pattern="[A-Za-z0-9_-]{43}" required /></label>}
      {registration && !setup && <label>{t.authInvitationCode}<input name="invitationCode" ref={invitationInput} autoComplete="off" autoCapitalize="none" spellCheck={false} minLength={43} maxLength={43} pattern="[A-Za-z0-9_-]{43}" required /></label>}
      {registration && !setup && <>
        <label>{it.email}<input type="email" name="email" maxLength={254} autoComplete="email" /></label>
        <button type="button" disabled={pending} onClick={async (event) => {
          const form = event.currentTarget.form;
          if (!form) return;
          const data = new FormData(form);
          setPending(true); setError(null); setVerificationSent(false);
          try {
            const response = await fetch("/api/auth/registration-email", { method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ invitationCode: data.get("invitationCode"), email: data.get("email") }), signal: AbortSignal.timeout(20_000) });
            if (!response.ok) setError("authNetworkError"); else setVerificationSent(true);
          } catch { setError("authNetworkError"); } finally { setPending(false); }
        }}>{it.send}</button>
        <label>{it.code}<input name="emailProof" minLength={43} maxLength={43} autoComplete="off" /></label>
        {verificationSent && <p role="status">{it.sent}</p>}
      </>}
      {error && <p className="auth-error" role="alert">{t[error]}</p>}
      <button disabled={pending} type="submit">{pending ? t.authPending : setup ? t.authSetup : registration ? t.authSignupTitle : t.authLogin}</button>
    </form>
  );
}
