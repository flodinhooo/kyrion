"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";

export function SessionStatus() {
  const { t } = useWorkspace();
  const [expired, setExpired] = useState(false);
  useEffect(() => {
    let disposed = false;
    let busy = false;
    const controller = new AbortController();
    async function check() {
      if (busy || document.visibilityState === "hidden") return;
      busy = true;
      try {
        const response = await fetch("/api/auth/me", { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(8_000)]) });
        if (!disposed && (response.ok || response.status === 401)) setExpired(response.status === 401);
      } catch { /* An unavailable service is not an expired session. */ }
      finally { busy = false; }
    }
    const timer = window.setInterval(() => void check(), 60_000);
    window.addEventListener("focus", check);
    return () => { disposed = true; controller.abort(); window.clearInterval(timer); window.removeEventListener("focus", check); };
  }, []);
  return expired ? <div className="session-status" role="alert"><span>{t.sessionExpired}</span><Link href="/login">{t.authLogin}</Link></div> : null;
}
