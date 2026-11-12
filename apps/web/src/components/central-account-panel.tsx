"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { csrfHeader } from "@/features/auth/csrf";
import { isCentralDevice, isCentralStatus, type CentralDevice, type CentralStatus } from "@/features/auth/central-contracts";
import { centralMessages } from "@/features/auth/central-messages";
import type { Locale } from "@/lib/messages";
import { centralWebsite } from "@/features/auth/central-website";

export function CentralAccountPanel({ locale, login = false }: { locale: Locale; login?: boolean }) {
  const t = centralMessages[locale];
  const router = useRouter();
  const [enabled, setEnabled] = useState(false);
  const [status, setStatus] = useState<CentralStatus | null>(null);
  const [device, setDevice] = useState<CentralDevice | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [started, setStarted] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pollDelay, setPollDelay] = useState(5);
  const [finishing, setFinishing] = useState(false);
  const [copied, setCopied] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const config = await fetch("/api/auth/central/config", { cache: "no-store", signal: AbortSignal.timeout(10_000) });
      const value: unknown = await config.json();
      if (!config.ok || !value || typeof value !== "object" || !("enabled" in value) || typeof value.enabled !== "boolean") throw new Error();
      setEnabled(value.enabled);
      if (!login) {
        let response = await fetch("/api/auth/central/account", {
          cache: "no-store",
          signal: AbortSignal.timeout(10_000)
        });
        if (response.status === 404) response = await fetch("/api/auth/central/status", {
          cache: "no-store",
          signal: AbortSignal.timeout(10_000)
        });
        const current: unknown = await response.json();
        if (!response.ok || !isCentralStatus(current)) throw new Error();
        setStatus(current);
      }
    } catch { if (!login) setError("CORE_UNAVAILABLE"); }
  }, [login]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);

  useEffect(() => {
    if (login) return;
    const update = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    window.addEventListener("focus", update);
    const timer = status?.linked && status.directoryState === "pending" ? window.setInterval(update, 5000) : null;
    return () => {
      window.removeEventListener("focus", update);
      if (timer !== null) clearInterval(timer);
    };
  }, [login, refresh, status?.linked, status?.directoryState]);

  async function request(action: string, body: unknown, method = "POST") {
    await fetch("/api/auth/csrf", { cache: "no-store", signal: AbortSignal.timeout(10_000) });
    return fetch(`/api/auth/central/${action}`, {
      method, headers: { ...csrfHeader(), "Content-Type": "application/json" }, body: JSON.stringify(body),
      cache: "no-store", signal: AbortSignal.timeout(20_000),
    });
  }

  useEffect(() => {
    if (!device || confirmed) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      if (Date.now() >= Date.parse(device!.expiresAt)) {
        setDevice(null); setError("CENTRAL_OPERATION_INVALID"); return;
      }
      try {
        const response = await request("poll", {});
        const value: unknown = await response.json();
        if (!active) return;
        const code = value && typeof value === "object" && "code" in value && typeof value.code === "string" ? value.code : "";
        if (code === "CENTRAL_SLOW_DOWN") { setPollDelay((delay) => delay + 5); return; }
        if (!response.ok) { setDevice(null); setError(code || "UNKNOWN"); return; }
        if (value && typeof value === "object" && "status" in value && value.status === "CONFIRM") {
          if (login) { setConfirmed(true); return; }
          setFinishing(true);
          try {
            const completed = await request("complete", { confirm: true });
            if (!active) return;
            if (!completed.ok) {
              const result: unknown = await completed.json();
              setError(result && typeof result === "object" && "code" in result && typeof result.code === "string" ? result.code : "UNKNOWN");
              setDevice(null); return;
            }
            setFinishing(false); setDevice(null); setStarted(false); setNotice(t.saved); await refresh();
          } finally { if (active) setFinishing(false); }
          return;
        }
        timer = setTimeout(() => { void poll(); }, pollDelay * 1_000);
      } catch {
        if (active) { setDevice(null); setError("CENTRAL_UNAVAILABLE"); }
      }
    }
    timer = setTimeout(() => { void poll(); }, pollDelay * 1_000);
    return () => { active = false; clearTimeout(timer); };
  }, [device, confirmed, pollDelay, login, refresh, t.saved]);

  async function start(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (busy || finishing) return;
    const form = event?.currentTarget;
    const password = form ? new FormData(form).get("currentPassword") : undefined;
    form?.reset();
    setBusy(true); setError(""); setNotice("");
    try {
      const response = await request("start", { mode: login ? "LOGIN" : "LINK", ...(login ? {} : { currentPassword: password }) });
      const value: unknown = await response.json();
      if (!response.ok || !isCentralDevice(value)) {
        setError(value && typeof value === "object" && "code" in value && typeof value.code === "string" ? value.code : "UNKNOWN"); return;
      }
      setDevice(value); setPollDelay(value.interval); setConfirmed(false); setStarted(true); setCopied(false); setFinishing(false);
    } catch { setError("CENTRAL_UNAVAILABLE"); } finally { setBusy(false); }
  }

  async function finish(action: "complete" | "cancel") {
    if (busy) return;
    setBusy(true); setError("");
    try {
      const response = await request(action, action === "complete" ? { confirm: true } : {});
      if (!response.ok) {
        const value: unknown = await response.json();
        setError(value && typeof value === "object" && "code" in value && typeof value.code === "string" ? value.code : "UNKNOWN");
        return;
      }
      setDevice(null); setConfirmed(false); setStarted(false);
      if (action === "complete") {
        if (login) { router.replace("/"); router.refresh(); }
        else { setNotice(t.saved); await refresh(); }
      }
    } catch { setError("CENTRAL_UNAVAILABLE"); } finally { setBusy(false); }
  }

  async function unlink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    if (data.get("confirm") !== "on") return;
    form.reset(); setBusy(true); setError(""); setNotice("");
    try {
      const response = await request("link", { currentPassword: data.get("currentPassword") }, "DELETE");
      if (!response.ok) {
        const value: unknown = await response.json();
        setError(value && typeof value === "object" && "code" in value && typeof value.code === "string" ? value.code : "UNKNOWN"); return;
      }
      setNotice(t.saved); await refresh(); router.refresh();
    } catch { setError("CORE_UNAVAILABLE"); } finally { setBusy(false); }
  }

  if (login && !enabled) return null;
  const website = device && !login ? centralWebsite(device.verificationUri, locale) : null;
  const errorText = error in t.errors ? t.errors[error as keyof typeof t.errors] : t.error;
  return <section className={login ? "central-account-panel" : "settings-link-card profile-security-panel account-link-panel"} aria-label={t.title}>
    {!login && <><h2>{t.title}</h2><p>{status === null ? t.checking : status.linked ? t.connected : t.disconnected}</p><p>{t.localHelp}</p></>}
    {!login && status?.linked && <div className="account-link-identity">
      <span>{t.connectedAccount}</span>
      <strong>{status.account?.email ?? status.account?.displayName ?? t.identityMissing}</strong>
      {status.account?.email && status.account.displayName && status.account.displayName !== status.account.email &&
        <p>{status.account.displayName}</p>}
      {status.linkedAt &&
        <small>{t.connectedSince}: {new Intl.DateTimeFormat(locale, {dateStyle: "medium"}).format(new Date(status.linkedAt))}</small>}
      <small>{status.directoryState === "confirmed" ? t.directoryConfirmed : status.directoryState === "pending" ? t.directoryPending : t.directoryUnavailable}</small>
      <a href={`https://www.kyrion.ch${locale === "en" ? "/en" : ""}/account`} target="_blank"
         rel="noopener noreferrer">{t.viewInstallations}</a>
    </div>}
    {!login && !enabled && <p>{t.disabled}</p>}
    {error && <p role="alert" className="auth-error">{errorText}</p>}
    {notice && <p role="status">{notice}</p>}
    {!device && !status?.linked && enabled && (login || status !== null) && (login
      ? <button type="button" disabled={busy} onClick={() => void start()}>{busy ? t.checking : t.login}</button>
      : <form className="auth-form" onSubmit={start}><label>{t.password}<input name="currentPassword" type="password" autoComplete="current-password" minLength={12} maxLength={200} required /></label><button type="submit" disabled={busy}>{busy ? t.checking : t.connect}</button></form>)}
    {device && <div className="auth-form">
      <p>{website ? t.websiteHelp : t.deviceHelp}</p>
      <div className="account-link-code"><span>{t.code}</span><code>{device.userCode}</code></div>
      <div className="account-link-actions">
        <button type="button" className="account-link-copy" disabled={finishing} onClick={async () => {
          try { await navigator.clipboard.writeText(device.userCode); setCopied(true); }
          catch { setNotice(t.copyFailed); }
        }}>{copied ? t.copied : t.copyCode}</button>
        <a className="account-link-open" href={website ?? device.verificationUri} target="_blank" rel="noopener noreferrer">{website ? t.openWebsite : t.openProvider}</a>
      </div>
      <p role="status">{finishing ? t.finishing : confirmed ? (login ? t.loginConfirmed : t.confirmed) : t.waiting}</p>
      {confirmed && <button type="button" disabled={busy} onClick={() => void finish("complete")}>{login ? t.confirmLogin : t.confirmLink}</button>}
      <button type="button" disabled={busy || finishing} onClick={() => void finish("cancel")}>{t.cancel}</button>
    </div>}
    {!device && started && <button type="button" disabled={busy} onClick={() => void finish("cancel")}>{t.cancel}</button>}
    {!login && status?.linked && <form className="auth-form" onSubmit={unlink}>
      <p>{t.unlinkHelp}</p><label>{t.password}<input name="currentPassword" type="password" autoComplete="current-password" minLength={12} maxLength={200} required /></label>
      <label><span><input name="confirm" type="checkbox" required /> {t.confirmUnlink}</span></label>
      <button type="submit" disabled={busy}>{busy ? t.checking : t.unlink}</button>
    </form>}
  </section>;
}
