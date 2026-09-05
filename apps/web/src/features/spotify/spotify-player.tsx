"use client";

import Link from "next/link";
import Image from "next/image";
import { Music2, Pause, Play, RefreshCw, SkipBack, SkipForward, Speaker, Volume2 } from "lucide-react";
import { useWorkspace } from "@/components/app-shell";
import { useSpotifyPlayer } from "./use-spotify-player";

function time(ms: number) {
  const seconds = Math.floor(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export function SpotifyPlayer() {
  const { t } = useWorkspace();
  const { status, devices, playback, error, pending, refresh, control, transfer } = useSpotifyPlayer();
  const device = devices.find((entry) => entry.id === playback?.deviceId) ?? devices.find((entry) => entry.active);
  const disabled = pending || error || !device || device.restricted;
  const blocked = (action: string) => playback?.disallowed.includes(action) ?? false;
  return <div className="lounge-player" aria-busy={pending}>
    <div className="lounge-source-heading">
      <span className="lounge-source-name"><span className="lounge-service-mark spotify-mark"><Music2 size={22} /></span>Spotify</span>
      <span className="lounge-badge">{status?.connected ? t.loungeConnected : t.loungeConnectAccount}</span>
    </div>
    {error && <div className="lounge-error" role="alert"><p>{t.spotifyError}</p><button disabled={pending} onClick={() => void refresh()}><RefreshCw size={16} />{t.loungeRetry}</button></div>}
    {!status ? (!error && <p role="status">{t.spotifyLoading}</p>) : !status.connected ? <div className="lounge-empty">
      <Music2 size={56} strokeWidth={1} /><h2>{t.loungeSpotifyWelcome}</h2><p>{t.loungeSpotifySetup}</p>
      <Link className="lounge-primary" href="/plugins/spotify">{t.spotifyConnect}</Link>
    </div> : <>
      <div className="lounge-now-playing">
        <div className="lounge-artwork">{playback?.imageUrl ? <Image unoptimized src={playback.imageUrl} alt="" width={240} height={240} /> : <Music2 size={72} strokeWidth={1} />}</div>
        <div className="lounge-track"><p className="eyebrow">{playback?.playing ? t.loungePlaying : t.loungeReady}</p>
          <h2>{playback?.title ?? t.loungeNothingPlaying}</h2><p>{playback?.artist ?? t.loungeResumeHint}</p>
          <a href={playback?.trackUrl ?? "https://open.spotify.com"} target="_blank" rel="noreferrer">{t.loungeOpenSpotify} ↗</a>
        </div>
      </div>
      <div className="lounge-progress"><progress aria-label={t.loungeProgress} max={playback?.durationMs || 1} value={Math.min(playback?.progressMs ?? 0, playback?.durationMs ?? 0)} /><div><span>{time(playback?.progressMs ?? 0)}</span><span>{time(playback?.durationMs ?? 0)}</span></div></div>
      <div className="lounge-transport">
        <button aria-label={t.loungePrevious} disabled={disabled || blocked("skipping_prev")} onClick={() => device && void control({ action: "PREVIOUS", deviceId: device.id })}><SkipBack /></button>
        <button className="lounge-play" aria-label={playback?.playing ? t.loungePause : t.loungePlay} disabled={disabled || blocked(playback?.playing ? "pausing" : "resuming")} onClick={() => device && void control({ action: playback?.playing ? "PAUSE" : "RESUME", deviceId: device.id })}>{playback?.playing ? <Pause /> : <Play />}</button>
        <button aria-label={t.loungeNext} disabled={disabled || blocked("skipping_next")} onClick={() => device && void control({ action: "NEXT", deviceId: device.id })}><SkipForward /></button>
      </div>
      <div className="lounge-output">
        <label><span><Speaker size={17} />{t.loungeOutput}</span><select value={device?.id ?? ""} disabled={pending || error || blocked("transferring_playback") || devices.length === 0} onChange={(event) => void transfer(event.target.value)}>
          <option value="" disabled>{t.loungeChooseDevice}</option>
          {devices.map((entry) => <option key={entry.id} value={entry.id} disabled={entry.restricted}>{entry.name}{entry.active ? ` · ${t.spotifyActive}` : ""}</option>)}
        </select></label>
        <label><span><Volume2 size={17} />{t.loungeVolume} {device?.volumePercent !== null && device?.volumePercent !== undefined ? `${device.volumePercent}%` : ""}</span>
          <input key={`${device?.id}-${device?.volumePercent}`} type="range" min="0" max="100" defaultValue={device?.volumePercent ?? 0} disabled={disabled || !device?.supportsVolume || device?.volumePercent === null}
            onPointerUp={(event) => device && void control({ action: "VOLUME", deviceId: device.id, volumePercent: Number(event.currentTarget.value) })}
            onKeyUp={(event) => { if (device && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End", "PageUp", "PageDown"].includes(event.key)) void control({ action: "VOLUME", deviceId: device.id, volumePercent: Number(event.currentTarget.value) }); }} />
        </label>
      </div>
      {devices.length === 0 && <p className="lounge-hint">{t.spotifyNoDevices}</p>}
      <div className="lounge-player-footer"><Link href="/plugins/spotify">{t.loungeManageConnection}</Link><button disabled={pending} onClick={() => void refresh()} aria-label={t.loungeRefresh}><RefreshCw size={16} /></button></div>
    </>}
  </div>;
}
