export function playbackPosition(progressMs: number, durationMs: number, elapsedMs: number, playing: boolean) {
  return Math.min(durationMs, Math.max(0, progressMs + (playing ? Math.max(0, elapsedMs) : 0)));
}
