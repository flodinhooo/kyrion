"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { csrfHeader } from "@/features/auth/csrf";
import { isSpotifyDeviceList, isSpotifyPlayback, isSpotifyStatus, type SpotifyDevice, type SpotifyPlayback, type SpotifyPlaybackCommand, type SpotifyStatus } from "./contracts";

async function read(path: string, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(`/api/integrations/spotify${path}`, { cache: "no-store", signal });
  if (!response.ok) throw new Error("Playback unavailable");
  return response.json();
}

export function useSpotifyPlayer() {
  const [status, setStatus] = useState<SpotifyStatus | null>(null);
  const [devices, setDevices] = useState<SpotifyDevice[]>([]);
  const [playback, setPlayback] = useState<SpotifyPlayback | null>(null);
  const [error, setError] = useState(false);
  const [pending, setPending] = useState(false);
  const busy = useRef(false);
  const mounted = useRef(false);
  const loading = useRef<AbortController | null>(null);

  const refresh = useCallback(async () => {
    loading.current?.abort();
    const controller = new AbortController();
    loading.current = controller;
    const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]);
    try {
      const nextStatus = await read("", signal);
      if (!isSpotifyStatus(nextStatus)) throw new Error("Invalid status");
      if (controller.signal.aborted || !mounted.current) return;
      setStatus(nextStatus);
      if (nextStatus.connected) {
        const [nextDevices, nextPlayback] = await Promise.all([read("/devices", signal), read("/playback", signal)]);
        if (!isSpotifyDeviceList(nextDevices) || !isSpotifyPlayback(nextPlayback)) throw new Error("Invalid playback");
        if (controller.signal.aborted || !mounted.current) return;
        setDevices(nextDevices);
        setPlayback(nextPlayback);
      } else {
        setDevices([]);
        setPlayback(null);
      }
      setError(false);
    } catch {
      if (!controller.signal.aborted && mounted.current) setError(true);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    // Poll only while visible. Selecting a different source never sends a player command.
    const poll = () => { if (!document.hidden && !busy.current) void refresh(); };
    const initial = window.setTimeout(poll, 0);
    const timer = window.setInterval(poll, 15000);
    document.addEventListener("visibilitychange", poll);
    return () => {
      mounted.current = false;
      loading.current?.abort();
      window.clearTimeout(initial);
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", poll);
    };
  }, [refresh]);

  async function send(path: string, body: SpotifyPlaybackCommand | { deviceId: string; play: boolean }) {
    if (busy.current) return;
    busy.current = true;
    loading.current?.abort();
    setPending(true);
    setError(false);
    try {
      const response = await fetch(`/api/integrations/spotify/playback${path}`, {
        method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify(body), signal: AbortSignal.timeout(15000),
      });
      if (!response.ok) throw new Error("Playback command failed");
      if (mounted.current) await refresh();
    } catch { if (mounted.current) setError(true); }
    finally { busy.current = false; if (mounted.current) setPending(false); }
  }

  return { status, devices, playback, error, pending, refresh,
    control: (command: SpotifyPlaybackCommand) => send("", command),
    transfer: (deviceId: string) => send("/device", { deviceId, play: playback?.playing ?? false }),
  };
}
