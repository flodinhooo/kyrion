"use client";

import Link from "next/link";
import {useEffect, useState} from "react";
import {recoveryMessages} from "@/features/system-services/recovery-messages";

type Job = {
  state: "idle" | "running" | "completed" | "failed";
  correlationId: string | null;
  results: { id: string; result: "started" | "already_running" | "failed" }[]
};

function isJob(value: unknown): value is Job {
  if (!value || typeof value !== "object" || !("state" in value) || !("results" in value) || !("correlationId" in value)) return false;
  return ["idle", "running", "completed", "failed"].includes(String(value.state))
    && (value.correlationId === null || typeof value.correlationId === "string")
    && Array.isArray(value.results) && value.results.length <= 9 && value.results.every((item: unknown) =>
      !!item && typeof item === "object" && "id" in item && typeof item.id === "string" && "result" in item
      && ["started", "already_running", "failed"].includes(String(item.result)));
}

export default function RecoveryPage() {
  const [locale, setLocale] = useState<"de" | "en">("de");
  const [key, setKey] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const t = recoveryMessages[locale];

  async function send(action: "start" | "restart" | "status") {
    if (action === "restart" && !window.confirm(t.confirm)) return;
    setBusy(true);
    setError(false);
    try {
      const response = await fetch("/api/dev-recovery", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({key, action})
      });
      const value: unknown = await response.json();
      if (!response.ok || !isJob(value)) throw new Error("Recovery failed");
      setJob(value);
    } catch {
      setError(true);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (job?.state !== "running") return;
    const controller = new AbortController();
    const timer = window.setInterval(() => {
      void fetch("/api/dev-recovery", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({key, action: "status"}),
        signal: controller.signal
      })
        .then(async (response) => {
          const value: unknown = await response.json();
          if (!response.ok || !isJob(value)) throw new Error("Invalid recovery status");
          setJob(value);
          setError(false);
        }).catch(() => {
          if (!controller.signal.aborted) setError(true);
        });
    }, 3000);
    return () => {
      controller.abort();
      window.clearInterval(timer);
    };
  }, [job?.state, key]);
  const disabled = busy || job?.state === "running";
  return <main className="auth-stage">
    <section className="auth-card">
      <button type="button" className="language-button" aria-label={t.language}
              onClick={() => setLocale(locale === "de" ? "en" : "de")}>{locale.toUpperCase()}</button>
      <h1>{t.title}</h1><p>{t.description}</p><p>{t.keyHint}</p>
      <div className="auth-form">
        <label>{t.key}<input type="password" autoComplete="off" maxLength={64} value={key} disabled={disabled}
                             onChange={(event) => setKey(event.target.value.trim())}/></label>
        <button type="button" disabled={disabled || !/^[a-f0-9]{64}$/.test(key)}
                onClick={() => void send("start")}>{t.start}</button>
        <button type="button" disabled={disabled || !/^[a-f0-9]{64}$/.test(key)}
                onClick={() => void send("restart")}>{t.restart}</button>
        <button type="button" disabled={busy || !/^[a-f0-9]{64}$/.test(key)}
                onClick={() => void send("status")}>{t.check}</button>
      </div>
      {error && <p role="alert">{t.error}</p>}
      {job && <div role="status"><p>{t[job.state]}</p>
        <ul>{job.results.map((item) => <li key={item.id}>{item.id}: {t[item.result]}</li>)}</ul>
        <code>{job.correlationId}</code></div>}
      <Link href="/login">{t.back}</Link>
    </section>
  </main>;
}
