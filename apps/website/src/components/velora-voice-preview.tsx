"use client";

import { Pause, Play, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { Locale } from "@/lib/site";

type VeloraVoicePreviewProps = {
  locale: Locale;
  label: string;
  speakingLabel: string;
  voiceNote: string;
  unavailableLabel: string;
  welcomedLabel: string;
};

const activeAudio = { element: null as HTMLAudioElement | null };
const barHeights = [18, 31, 24, 47, 66, 38, 74, 52, 30, 62, 42, 22];

export function VeloraVoicePreview({
  locale,
  label,
  speakingLabel,
  voiceNote,
  unavailableLabel,
  welcomedLabel,
}: VeloraVoicePreviewProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [state, setState] = useState<"idle" | "playing" | "error">("idle");
  const [showToast, setShowToast] = useState(false);
  const source = `/audio/velora-intro-${locale}.mp3`;

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    audio.pause();
    audio.currentTime = 0;
    setState("idle");
    if (activeAudio.element === audio) activeAudio.element = null;
  }, [locale]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onPlay = () => setState("playing");
    const onPause = () => setState("idle");
    const onEnded = () => {
      audio.currentTime = 0;
      setState("idle");
      if (activeAudio.element === audio) activeAudio.element = null;
    };
    const onError = () => {
      // A rejected hover attempt can dispatch its error after the user has
      // already started playback with a click. Never show that stale error.
      if (!audio.paused) return;
      setState("error");
      if (activeAudio.element === audio) activeAudio.element = null;
    };
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("error", onError);
    return () => {
      audio.pause();
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("error", onError);
      if (activeAudio.element === audio) activeAudio.element = null;
    };
  }, []);

  async function play() {
    const audio = audioRef.current;
    if (!audio) return;
    if (activeAudio.element && activeAudio.element !== audio) {
      activeAudio.element.pause();
      activeAudio.element.currentTime = 0;
    }
    activeAudio.element = audio;
    setState("idle");
    try {
      await audio.play();
      setShowToast(true);
    } catch {
      if (activeAudio.element === audio) activeAudio.element = null;
      setState("error");
    }
  }

  function toggle() {
    const audio = audioRef.current;
    if (!audio) return;
    if (!audio.paused) {
      audio.pause();
      audio.currentTime = 0;
      return;
    }
    void play();
  }

  const isPlaying = state === "playing";
  return (
    <div className="mt-8">
      <audio ref={audioRef} preload="none" src={source} />
      <button
        type="button"
        onClick={toggle}
        onMouseEnter={() => {
          if (audioRef.current?.paused) void play();
        }}
        onFocus={() => {
          if (audioRef.current?.paused) void play();
        }}
        aria-label={isPlaying ? speakingLabel : label}
        className="group/voice flex min-h-20 w-full max-w-md touch-manipulation flex-col items-start gap-4 rounded-xl border border-border bg-background/45 px-5 py-4 text-left transition-colors hover:border-accent/50 focus-visible:border-accent"
      >
        <span
          onClick={(event) => {
            event.stopPropagation();
            toggle();
          }}
          className={`flex h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-lg transition-[filter,opacity] group-hover/voice:brightness-110 ${isPlaying ? "velora-wave-playing" : ""}`}
          aria-hidden="true"
        >
          {barHeights.map((height, index) => (
            <span
              key={index}
              className="velora-wave-bar core-line w-1 rounded-full opacity-60"
              style={{
                height: `${height}%`,
                animationDelay: `${index * 75}ms`,
              }}
            />
          ))}
        </span>
        <span className="flex w-full items-center justify-between gap-4">
          <span className="flex items-center gap-2.5 text-sm font-medium">
            {isPlaying ? (
              <Pause className="size-4 text-accent" aria-hidden="true" />
            ) : (
              <Play className="size-4 text-accent" aria-hidden="true" />
            )}
            {isPlaying ? speakingLabel : label}
          </span>
          <span className="flex items-center gap-2 font-mono text-[10px] text-muted-foreground">
            <Volume2 className="size-3.5" aria-hidden="true" />
            {voiceNote}
          </span>
        </span>
      </button>
      <div
        role="status"
        aria-live="polite"
        className={`pointer-events-none fixed right-5 bottom-5 z-50 rounded-lg border border-accent/40 bg-card px-4 py-3 font-mono text-xs text-foreground shadow-lg transition-[opacity,transform] duration-300 ${showToast ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"}`}
        onTransitionEnd={() => {
          if (showToast) window.setTimeout(() => setShowToast(false), 2200);
        }}
      >
        {welcomedLabel}
      </div>
      {state === "error" && (
        <p className="mt-2 font-mono text-[10px] leading-5 text-muted-foreground">
          {unavailableLabel}
        </p>
      )}
    </div>
  );
}
