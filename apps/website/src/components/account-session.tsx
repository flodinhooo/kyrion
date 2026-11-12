"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type AccountStatus = {
  enabled: boolean;
  session: { id: string; csrf: string; expiresAt: string } | null;
};
type AccountContext = {
  status: AccountStatus | null;
  error: boolean;
  busy: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
};
const Context = createContext<AccountContext | null>(null);

function readStatus(value: unknown): AccountStatus {
  if (
    !value ||
    typeof value !== "object" ||
    !("enabled" in value) ||
    typeof value.enabled !== "boolean"
  )
    throw new Error("Invalid account status");
  if (!value.enabled) return { enabled: false, session: null };
  if (!("session" in value) || value.session === null)
    return { enabled: true, session: null };
  const s = value.session;
  if (
    !s ||
    typeof s !== "object" ||
    !("id" in s) ||
    typeof s.id !== "string" ||
    !("csrf" in s) ||
    typeof s.csrf !== "string" ||
    !("expiresAt" in s) ||
    typeof s.expiresAt !== "string" ||
    !Number.isFinite(Date.parse(s.expiresAt))
  )
    throw new Error("Invalid account session");
  return {
    enabled: true,
    session: { id: s.id, csrf: s.csrf, expiresAt: s.expiresAt },
  };
}

export function AccountSessionProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AccountStatus | null>(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const revision = useRef(0);
  const loggingOut = useRef(false);
  const invalidate = useCallback(() => {
    revision.current++;
  }, []);
  const refresh = useCallback(async () => {
    if (loggingOut.current) return;
    const version = ++revision.current;
    try {
      const response = await fetch("/api/account/session", {
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      });
      if (!response.ok) throw new Error();
      const value = readStatus(await response.json());
      if (version === revision.current) {
        setStatus(value);
        setError(false);
      }
    } catch {
      if (version === revision.current) setError(true);
    }
  }, []);
  useEffect(() => {
    const initial = window.setTimeout(() => {
      void refresh();
    }, 0);
    const visible = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    const timer = window.setInterval(visible, 60000);
    window.addEventListener("focus", visible);
    document.addEventListener("visibilitychange", visible);
    return () => {
      invalidate();
      clearTimeout(initial);
      clearInterval(timer);
      window.removeEventListener("focus", visible);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [refresh, invalidate]);
  async function logout() {
    if (loggingOut.current || !status?.session) return;
    loggingOut.current = true;
    revision.current++;
    setBusy(true);
    try {
      const response = await fetch("/api/account/logout", {
        method: "POST",
        headers: { "x-kyrion-csrf": status.session.csrf },
        signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) throw new Error();
      setStatus({ enabled: true, session: null });
      setError(false);
    } catch {
      setError(true);
    } finally {
      loggingOut.current = false;
      setBusy(false);
    }
  }
  return (
    <Context.Provider value={{ status, error, busy, refresh, logout }}>
      {children}
    </Context.Provider>
  );
}

export function useAccountSession() {
  const value = useContext(Context);
  if (!value) throw new Error("Account session provider missing");
  return value;
}
