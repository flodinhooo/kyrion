"use client";

import {useCallback, useEffect, useState} from "react";
import {useWorkspace} from "@/components/app-shell";
import {csrfHeader} from "@/features/auth/csrf";
import {knowledgeMessages, knowledgeError} from "@/features/knowledge/messages";

type Document = { id: string; originalFilename: string; status: string; errorCode: string | null };

function isDocument(value: unknown): value is Document {
  if (!value || typeof value !== "object") return false;
  const d = value as Partial<Document>;
  return typeof d.id === "string" && /^[0-9a-f-]{36}$/.test(d.id) && typeof d.originalFilename === "string"
    && typeof d.status === "string" && d.status in knowledgeMessages.en.statuses
    && (d.errorCode === null || typeof d.errorCode === "string");
}

export function KnowledgeView() {
  const {locale, hasPermission} = useWorkspace();
  const t = knowledgeMessages[locale];
  const [space, setSpace] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/knowledge/spaces", {cache: "no-store"});
      const spaces: unknown = await response.json();
      if (!response.ok || !Array.isArray(spaces)) throw new Error("CORE_UNAVAILABLE");
      const first: unknown = spaces[0];
      const id = first && typeof first === "object" && "id" in first && typeof first.id === "string"
      && /^[0-9a-f-]{36}$/.test(first.id) ? first.id : null;
      setSpace(id);
      if (id) {
        const list = await fetch(`/api/knowledge/spaces/${id}/documents?limit=25&offset=${offset}`, {cache: "no-store"});
        const value: unknown = await list.json();
        if (!list.ok || !Array.isArray(value) || !value.every(isDocument)) throw new Error("CORE_UNAVAILABLE");
        setDocuments(value);
      }
    } catch {
      setError("CORE_UNAVAILABLE");
    } finally {
      setLoading(false);
    }
  }, [offset]);
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 5000);
    return () => clearInterval(timer);
  }, [load]);

  async function mutate(path: string, method: string, body?: FormData) {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/knowledge/${path}`, {method, body, headers: csrfHeader()});
      if (!response.ok) {
        const value: unknown = await response.json();
        throw new Error(value && typeof value === "object" && "code" in value && typeof value.code === "string" ? value.code : "UNKNOWN");
      }
      await load();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "UNKNOWN");
    } finally {
      setBusy(false);
    }
  }

  return <section className="settings-page">
    <h1>{t.title}</h1><p>{t.description}</p>
    {error && <p role="alert">{knowledgeError(locale, error)}</p>}
    {loading ? <p role="status">{t.loading}</p> : !space ?
      <button disabled={busy || !hasPermission("knowledge:create")}
              onClick={() => void mutate("spaces", "POST")}>{t.create}</button> : <>
        {hasPermission("knowledge:create") && <form onSubmit={event => {
          event.preventDefault();
          const form = event.currentTarget;
          void mutate(`spaces/${space}/documents`, "POST", new FormData(form)).then(() => form.reset());
        }}><label>{t.upload}<input type="file" name="file" accept="application/pdf,text/plain,.pdf,.txt" required
                                   disabled={busy}/></label>
          <button disabled={busy} type="submit">{busy ? t.loading : t.upload}</button>
        </form>}
        {documents.length === 0 && <p>{t.empty}</p>}
        <ul>{documents.map(document => <li key={document.id}>
          <strong>{document.originalFilename}</strong>{" · "}{t.statuses[document.status as keyof typeof t.statuses]}
          {document.errorCode && <p>{knowledgeError(locale, document.errorCode)}</p>}
          <a href={`/api/knowledge/documents/${document.id}/content`}>{t.open}</a>{" "}
          {hasPermission("knowledge:create") && <button disabled={busy}
                                                        onClick={() => void mutate(`documents/${document.id}/reindex`, "POST")}>{t.retry}</button>}{" "}
          {hasPermission("knowledge:delete") && <button disabled={busy} onClick={() => {
            if (window.confirm(t.confirm)) void mutate(`documents/${document.id}`, "DELETE");
          }}>{t.delete}</button>}
        </li>)}</ul>
        <button disabled={offset === 0} onClick={() => setOffset(n => Math.max(0, n - 25))}>{t.previous}</button>
        <button disabled={documents.length < 25} onClick={() => setOffset(n => n + 25)}>{t.next}</button>
      </>}
  </section>;
}
