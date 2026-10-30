"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import { identityMessages } from "@/features/spaces/identity-messages";
import { isBusinessPolicy, isDnsChallenge, isEmailIdentity, type BusinessPolicy, type DnsChallenge, type EmailIdentity } from "@/features/spaces/identity-contracts";
import { isSpace } from "@/features/spaces/contracts";
import "../space/space.css";

export default function IdentityPage() {
  const { locale, roles } = useWorkspace();
  const t = identityMessages[locale];
  const owner = roles.includes("OWNER");
  const [email, setEmail] = useState<EmailIdentity | null>(null);
  const [policy, setPolicy] = useState<BusinessPolicy | null>(null);
  const [challenge, setChallenge] = useState<DnsChallenge | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [business, setBusiness] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/identity/email", { signal: AbortSignal.timeout(10_000) });
      const value: unknown = await response.json();
      if (!response.ok || !isEmailIdentity(value)) throw new Error();
      setEmail(value);
      const me = await fetch("/api/auth/me", { signal: AbortSignal.timeout(10_000) });
      const user: unknown = await me.json();
      const isBusiness = !!user && typeof user === "object" && "user" in user && !!user.user && typeof user.user === "object"
        && "space" in user.user && isSpace(user.user.space) && user.user.space.type === "BUSINESS";
      setBusiness(isBusiness);
      if (owner && isBusiness) {
        const result = await fetch("/api/identity/business", { signal: AbortSignal.timeout(10_000) });
        const data: unknown = await result.json();
        if (!result.ok || !isBusinessPolicy(data)) throw new Error();
        setPolicy(data);
      }
    } catch { setError("UNKNOWN"); }
  }, [owner]);
  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  async function mutate(path: string, body: unknown, method = "POST") {
    if (busy) return;
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await fetch(`/api/identity/${path}`, { method, headers: { ...csrfHeader(), "Content-Type": "application/json" }, body: JSON.stringify(body), signal: AbortSignal.timeout(30_000) });
      const value: unknown = response.status === 204 || response.status === 202 ? null : await response.json();
      if (!response.ok) {
        setError(value && typeof value === "object" && "code" in value && typeof value.code === "string" ? value.code : "UNKNOWN"); return;
      }
      if (isDnsChallenge(value)) setChallenge(value);
      setNotice(path === "email" ? t.sent : t.saved);
      await refresh();
    } catch { setError("UNKNOWN"); }
    finally { setBusy(false); }
  }
  function submit(event: FormEvent<HTMLFormElement>, path: string, field: string) {
    event.preventDefault(); void mutate(path, { [field]: new FormData(event.currentTarget).get(field) });
  }
  function savePolicy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    void mutate("business", { mode: data.get("mode"), domains: data.getAll("domains"), confirmRevokeInvitations: data.get("confirm") === "on" }, "PUT");
  }
  const status = email?.status === "VERIFIED" ? t.verified : email?.status === "LOCALLY_ATTESTED" ? t.attested : email?.status === "PENDING" ? t.waiting : t.missing;
  const errorText = error in t.errors ? t.errors[error as keyof typeof t.errors] : t.error;

  return <section className="settings-stage space-page"><div className="settings-card">
    <h1>{t.title}</h1>
    {error && <p role="alert" className="auth-error">{errorText}</p>}
    {notice && <p role="status">{notice}</p>}
    <button type="button" disabled={busy} onClick={() => void refresh()}>{t.refresh}</button>
    {email && <>
      <h2>{t.email}</h2><p>{status}</p><p>{email.email}</p>
      {email.pendingEmail && <p>{t.pending}: {email.pendingEmail}</p>}
      {!email.smtpAvailable && <p>{t.smtpOff}</p>}
      <form className="auth-form" onSubmit={(event) => submit(event, "email", "email")}>
        <label>{t.email}<input type="email" name="email" maxLength={254} required autoComplete="email" /></label>
        <button type="submit" disabled={busy || !email.smtpAvailable}>{busy ? t.busy : t.send}</button>
      </form>
      {email.pendingEmail && <form className="auth-form" onSubmit={(event) => submit(event, "email/verify", "code")}>
        <label>{t.code}<input name="code" minLength={43} maxLength={43} autoComplete="off" required /></label>
        <button type="submit" disabled={busy}>{t.verify}</button>
      </form>}
    </>}
    {owner && <aside><h2>{t.recovery}</h2><p>{t.recoveryHelp}</p>{policy && <p>{policy.recoveryConfigured ? t.recoveryReady : t.recoveryMissing}</p>}</aside>}
    {owner && business && policy && <section>
      <h2>{t.domainTitle}</h2><p>{t.dnsHelp}</p>
      <form className="auth-form" onSubmit={(event) => submit(event, "business/challenge", "domain")}>
        <label>{t.domain}<input name="domain" maxLength={253} required /></label><button type="submit" disabled={busy}>{t.challenge}</button>
      </form>
      {challenge && <div className="auth-form"><label>{t.dnsName}<input readOnly value={challenge.name} /></label><label>{t.dnsValue}<input readOnly value={challenge.value} /></label><p>{new Date(challenge.expiresAt).toLocaleString(locale)}</p></div>}
      <form className="auth-form" onSubmit={(event) => submit(event, "business/verify", "domain")}>
        <label>{t.domain}<input name="domain" maxLength={253} required /></label><button type="submit" disabled={busy}>{t.checkDns}</button>
      </form>
      <ul>{policy.domains.map((domain) => <li key={domain.domain}>{domain.domain} <button type="button" disabled={busy} onClick={() => void mutate("business/suspend", { domain: domain.domain })}>{t.suspend}</button></li>)}</ul>
      <form className="auth-form" onSubmit={savePolicy} key={JSON.stringify(policy)}>
        <fieldset disabled={busy}>
          <label>{t.policy}<select name="mode" defaultValue={policy.mode}><option value="OFF">{t.off}</option><option value="STRICT">{t.strict}</option></select></label>
          {policy.domains.map((domain) => <label key={domain.domain}><span>{domain.domain} · {domain.status === "VERIFIED" ? t.domainVerified : t.domainPending}</span><span><input name="domains" type="checkbox" value={domain.domain} defaultChecked={domain.allowed} /> {t.allow}</span></label>)}
          <label><span><input type="checkbox" name="confirm" /> {t.confirm}</span></label>
          <button type="submit">{t.save}</button>
        </fieldset>
      </form>
    </section>}
  </div></section>;
}
