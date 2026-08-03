"use client";

import { FormEvent, useState } from "react";
import { csrfHeader } from "@/features/auth/csrf";
import { useWorkspace } from "@/components/app-shell";

export function PasswordChangeForm() {
  const { t } = useWorkspace();
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<"success" | "current" | "same" | "invalid" | null>(null);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const newPassword = String(data.get("newPassword") ?? "");
    if (newPassword !== data.get("confirmPassword")) { setResult("invalid"); return; }
    setPending(true); setResult(null);
    try {
      const response = await fetch("/api/auth/password", {
        method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ currentPassword: data.get("currentPassword"), newPassword }),
      });
      const body = await response.json().catch(() => ({})) as { code?: string };
      if (!response.ok) {
        setResult(body.code === "INVALID_CURRENT_PASSWORD" ? "current" : body.code === "PASSWORD_UNCHANGED" ? "same" : "invalid");
        return;
      }
      form.reset(); setResult("success");
    } finally { setPending(false); }
  }

  const message = result === "success" ? t.passwordChanged
    : result === "current" ? t.currentPasswordInvalid
    : result === "same" ? t.passwordUnchanged
    : result === "invalid" ? t.passwordInvalid : null;

  return (
    <form className="password-form" onSubmit={submit}>
      <label>{t.currentPassword}<input name="currentPassword" type="password" autoComplete="current-password" minLength={12} maxLength={200} required /></label>
      <label>{t.newPassword}<input name="newPassword" type="password" autoComplete="new-password" minLength={12} maxLength={200} required /></label>
      <label>{t.confirmPassword}<input name="confirmPassword" type="password" autoComplete="new-password" minLength={12} maxLength={200} required /></label>
      {message && <p className={result === "success" ? "form-success" : "auth-error"} role="status">{message}</p>}
      <button type="submit" disabled={pending}>{pending ? t.passwordChanging : t.changePassword}</button>
    </form>
  );
}
