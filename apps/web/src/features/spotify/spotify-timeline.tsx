"use client";

import { useEffect, useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import type { SpotifyPlayback } from "./contracts";
import { playbackPosition } from "./timeline";
function time(ms: number) { const seconds = Math.floor(ms / 1000); return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`; }

export function SpotifyTimeline({ playback, disabled, onSeek }: { playback: SpotifyPlayback | null; disabled: boolean; onSeek: (position: number) => void }) {
  const { t } = useWorkspace();
  const [elapsed, setElapsed] = useState(0);
  const [draft, setDraft] = useState<number | null>(null);
  useEffect(() => {
    const started = performance.now();
    const tick = () => setElapsed(performance.now() - started);
    const timer = window.setInterval(tick, 250);
    return () => window.clearInterval(timer);
  }, []);
  const duration = playback?.durationMs ?? 0;
  const position = draft ?? playbackPosition(playback?.progressMs ?? 0, duration, elapsed, playback?.playing ?? false);
  function commit(value: string) {
    if (!disabled && duration > 0) onSeek(Math.min(Math.max(0, duration - 1), Number(value)));
    setDraft(null);
  }
  return <div className="lounge-progress">
    <input className="spotify-seek" type="range" min="0" max={duration || 1} step="1000" value={position}
      aria-label={t.spotifySeek} aria-valuetext={`${time(position)} / ${time(duration)}`}
      disabled={disabled || !duration || (playback?.disallowed.includes("seeking") ?? false)}
      onChange={(event) => setDraft(Number(event.target.value))}
      onPointerUp={(event) => commit(event.currentTarget.value)} onPointerCancel={() => setDraft(null)}
      onKeyUp={(event) => { if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(event.key)) commit(event.currentTarget.value); }} />
    <div><span>{time(position)}</span><span>{time(duration)}</span></div>
  </div>;
}
