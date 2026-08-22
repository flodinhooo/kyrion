"use client";

import { useCallback, useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import { ActiveSession, isActiveSessionList } from "@/features/auth/session-contracts";

export function ActiveSessionsPanel() {
  const { locale, t } = useWorkspace();
  const [sessions, setSessions] = useState<ActiveSession[] | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/auth/sessions", { cache: "no-store" });
      const value: unknown = await response.json();
      if (!response.ok || !isActiveSessionList(value)) throw new Error("Invalid session response");
      setSessions(value); setError(false);
    } catch { setError(true); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  async function revoke(id: string) {
    setPendingId(id); setError(false);
    try {
      const response = await fetch(`/api/auth/sessions/${id}`, { method: "DELETE", headers: csrfHeader() });
      if (!response.ok) throw new Error("Session revocation failed");
      await load();
    } catch { setError(true); } finally { setPendingId(null); }
  }

  const date = (value: string) => new Intl.DateTimeFormat(locale, {
    dateStyle: "medium", timeStyle: "short",
  }).format(new Date(value));

  return (
    <div className="settings-link-card profile-sessions-panel">
      <div className="session-panel-heading">
        <strong>{t.profileSessions}</strong>
        <small>{t.profileSessionsDescription}</small>
      </div>
      {sessions === null && !error && <p className="placeholder-copy">{t.profileSessionsLoading}</p>}
      {error && <p className="auth-error" role="alert">{t.profileSessionsError}</p>}
      {sessions?.length === 0 && <p className="placeholder-copy">{t.profileSessionsEmpty}</p>}
      <ul className="session-list">
        {sessions?.map((session) => (
          <li key={session.id}>
            <div>
              <strong>{session.current ? t.profileSessionCurrent : t.profileSessionOther}</strong>
              <small>{t.profileSessionLastSeen}: {date(session.lastSeenAt)}</small>
              <small>{t.profileSessionCreated}: {date(session.createdAt)}</small>
              <small>{t.profileSessionExpires}: {date(session.expiresAt)}</small>
            </div>
            {session.current
              ? <span className="session-current-badge">{t.profileSessionThisDevice}</span>
              : <button type="button" disabled={pendingId !== null} onClick={() => void revoke(session.id)}>
                  {pendingId === session.id ? t.profileSessionRevoking : t.profileSessionRevoke}
                </button>}
          </li>
        ))}
      </ul>
    </div>
  );
}
