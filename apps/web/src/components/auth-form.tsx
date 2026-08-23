"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

export function AuthForm({ setup }: { setup: boolean }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setPending(true); setError(null);
    try {
      const response = await fetch(`/api/auth/${setup ? "setup" : "login"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: data.get("username"), password: data.get("password") }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { code?: string };
        setError(body.code === "UNAUTHENTICATED" ? "Benutzername oder Passwort ist falsch." :
          body.code === "SETUP_ALREADY_COMPLETED" ? "Die Einrichtung wurde bereits abgeschlossen." :
          body.code === "CORE_UNAVAILABLE" ? "Kyrion Core ist nicht erreichbar." :
          "Bitte prüfe Benutzername und Passwort.");
        return;
      }
      router.replace("/"); router.refresh();
    } finally { setPending(false); }
  }

  return (
    <form
      action={`/api/auth/${setup ? "setup" : "login"}`}
      className="auth-form"
      method="post"
      onSubmit={submit}
    >
      <label>Benutzername<input name="username" autoComplete="username" minLength={3} maxLength={120} pattern="[A-Za-z0-9._-]+" required /></label>
      <label>Passwort<input name="password" type="password" autoComplete={setup ? "new-password" : "current-password"} minLength={12} maxLength={200} required /></label>
      {setup && <small>Mindestens 12 Zeichen. Das erste Konto wird lokaler Owner dieser Installation.</small>}
      {error && <p className="auth-error" role="alert">{error}</p>}
      <button disabled={pending} type="submit">{pending ? "Bitte warten …" : setup ? "Kyrion einrichten" : "Anmelden"}</button>
    </form>
  );
}
