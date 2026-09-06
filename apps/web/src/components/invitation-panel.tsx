"use client";

import { useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";

export function InvitationPanel() {
  const { t, canInvite } = useWorkspace();
  const [code, setCode] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);

  async function create() {
    if (pending) return;
    setPending(true); setFailed(false);
    try {
      const response = await fetch("/api/auth/invitations", {
        method: "POST", headers: csrfHeader(), signal: AbortSignal.timeout(15_000),
      });
      const value: unknown = await response.json();
      if (!response.ok || !value || typeof value !== "object" || !("code" in value)
        || typeof value.code !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(value.code)) {
        setFailed(true); return;
      }
      setCode(value.code);
    } catch { setFailed(true); }
    finally { setPending(false); }
  }

  if (!canInvite) return null;
  return <div className="settings-link-card profile-security-panel">
    <span><strong>{t.invitationTitle}</strong><small>{t.invitationDescription}</small></span>
    <div className="password-form">
      {code && <>
        <label>{t.authInvitationCode}<input readOnly value={code} autoComplete="off" onFocus={(event) => event.currentTarget.select()} /></label>
        <p role="status">{t.invitationInstructions}</p>
      </>}
      {failed && <p className="auth-error" role="alert">{t.invitationFailed}</p>}
      <button type="button" disabled={pending} onClick={create}>{pending ? t.authPending : t.invitationCreate}</button>
    </div>
  </div>;
}
