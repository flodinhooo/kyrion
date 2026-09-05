"use client";

import { RefreshCw } from "lucide-react";
import { useWorkspace } from "@/components/app-shell";

export function SnapshotStatus({ error, loaded, busy, updatedAt, onReload }: {
  error: boolean;
  loaded: boolean;
  busy: boolean;
  updatedAt: Date | null;
  onReload: () => void;
}) {
  const { t, locale } = useWorkspace();
  return <div className={`snapshot-status${error ? " has-error" : ""}`}>
    <div>
      {error ? <p role="alert">{t.snapshotRequestFailed}{loaded ? ` ${t.snapshotMayBeStale}` : ""}</p>
        : !loaded ? <p role="status">{t.homeLoadingStatus}</p> : <p>{t.snapshotDescription}</p>}
      {updatedAt && <small>{t.snapshotLoadedAt} <time dateTime={updatedAt.toISOString()}>{new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "medium" }).format(updatedAt)}</time></small>}
    </div>
    <button type="button" disabled={busy} onClick={onReload}><RefreshCw aria-hidden="true" />{busy ? t.homeRefreshingStatus : error ? t.snapshotRetry : t.snapshotReload}</button>
  </div>;
}
