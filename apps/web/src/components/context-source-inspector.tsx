"use client";
import {useState} from "react";
import {useWorkspace} from "@/components/app-shell";
import {contextMessages} from "@/features/memory/context-messages";
import {isContextSources, type ContextSource} from "@/features/memory/contracts";

export function ContextSourceInspector({conversationId, turnId}: { conversationId: string; turnId: string }) {
  const {locale, t} = useWorkspace();
  const c = contextMessages[locale];
  const [sources, setSources] = useState<ContextSource[]>([]);
  const [error, setError] = useState(false);

  async function inspect() {
    try {
      const query = new URLSearchParams({conversationId, turnId});
      const response = await fetch(`/api/memory/context?${query}`, {cache: "no-store"});
      const value: unknown = await response.json();
      if (!response.ok || !isContextSources(value)) throw new Error("Invalid context sources");
      setSources(value);
      setError(false);
    } catch {
      setError(true);
    }
  }

  return <div>
    <button type="button" onClick={() => void inspect()}>{c.inspect}</button>
    {error && <p role="alert">{t.memoryError}</p>}
    {sources.length > 0 && <ul>{sources.map((source, i) => <li key={`${source.kind}:${i}`}>
      {c.sourceKinds[source.kind as keyof typeof c.sourceKinds] ?? source.kind}: {source.selected ? c.selected : c.excluded}
      {source.privacy === "blocked" ? ` / ${c.blocked}` : ` / ${c.local}`} / {source.estimatedTokens}
    </li>)}</ul>}
  </div>;
}
