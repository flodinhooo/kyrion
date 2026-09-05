"use client";

import { createContext, useContext, useId, useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { ExternalLink, Link2, MonitorPlay, X } from "lucide-react";
import Image from "next/image";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import { isYouTubeEmbed, type YouTubeEmbed, type YouTubeSource } from "./contracts";

export const LoungeSourceVisible = createContext(true);
function subscribeVisibility(callback: () => void) {
  document.addEventListener("visibilitychange", callback);
  return () => document.removeEventListener("visibilitychange", callback);
}

export function YouTubeCard({ source }: { source: YouTubeSource }) {
  const { t } = useWorkspace();
  const sourceVisible = useContext(LoungeSourceVisible);
  const documentVisible = useSyncExternalStore(subscribeVisibility, () => !document.hidden, () => false);
  const [url, setUrl] = useState("");
  const [embed, setEmbed] = useState<YouTubeEmbed | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<"link" | "service" | null>(null);
  const requestId = useRef(0);
  const id = useId();
  const music = source === "MUSIC";
  const name = music ? "YouTube Music" : "YouTube";
  const externalUrl = music ? "https://music.youtube.com" : "https://www.youtube.com";

  async function prepare(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const current = ++requestId.current;
    setPending(true); setError(null);
    try {
      const response = await fetch("/api/integrations/youtube/embed", {
        method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ url, source }), signal: AbortSignal.timeout(15000),
      });
      const body: unknown = await response.json();
      if (current !== requestId.current) return;
      if (!response.ok || !isYouTubeEmbed(body)) { setError(response.status === 400 ? "link" : "service"); return; }
      setEmbed(body);
    } catch { if (current === requestId.current) setError("service"); }
    finally { if (current === requestId.current) setPending(false); }
  }

  return <article className="lounge-player youtube-card">
    <div className="lounge-source-heading"><span className="lounge-source-name"><Image src={music ? "/branding/youtube/youtube-music.png" : "/branding/youtube/youtube.png"} alt="" width={36} height={36} />{name}</span><span className="lounge-badge">{t.youtubeBrowser}</span></div>
    <div className="youtube-intro"><p className="eyebrow">{music ? t.youtubeMusicEyebrow : t.youtubeVideoEyebrow}</p><h2>{music ? t.youtubeMusicTitle : t.youtubeVideoTitle}</h2><p>{music ? t.youtubeMusicDescription : t.youtubeVideoDescription}</p></div>
    <form className="youtube-form" onSubmit={(event) => void prepare(event)}>
      <label htmlFor={id}>{t.youtubeLinkLabel}</label>
      <div><input id={id} type="url" required maxLength={2048} value={url} onChange={(event) => setUrl(event.target.value)} placeholder={music ? "https://music.youtube.com/watch?v=…" : "https://www.youtube.com/watch?v=…"} aria-describedby={`${id}-privacy`} autoComplete="off" spellCheck={false} />
        <button className="lounge-primary" disabled={pending || !url.trim()} type="submit"><Link2 size={17} />{pending ? t.youtubeLoading : t.youtubeLoad}</button></div>
      <p id={`${id}-privacy`} className="youtube-note">{t.youtubePrivacy} <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">{t.youtubePrivacyLink}</a></p>
    </form>
    {error && <p className="lounge-error" role="alert">{error === "link" ? t.youtubeInvalidLink : t.youtubeUnavailable}</p>}
    {embed ? <div className="youtube-loaded">
      {/* Unmount hidden embeds: a source switch must never leave invisible YouTube audio playing. */}
      {sourceVisible && documentVisible && <iframe key={embed.embedUrl} className="youtube-frame" src={embed.embedUrl} title={t.youtubePlayerTitle} allow="encrypted-media; fullscreen; picture-in-picture" allowFullScreen referrerPolicy="strict-origin-when-cross-origin" />}
      <div className="youtube-player-actions"><a href={embed.watchUrl} target="_blank" rel="noreferrer">{music ? t.youtubeOpenMusic : t.youtubeOpen}<ExternalLink size={16} /></a><button onClick={() => { ++requestId.current; setPending(false); setEmbed(null); }}><X size={16} />{t.youtubeClose}</button></div>
      <p className="youtube-note">{t.youtubePlaybackHint}</p>
    </div> : <a className="youtube-discover" href={externalUrl} target="_blank" rel="noreferrer"><MonitorPlay size={32} /><span><strong>{music ? t.youtubeOpenMusic : t.youtubeOpen}</strong><span>{t.youtubeDiscoverHint}</span></span><ExternalLink size={18} /></a>}
    <p className="youtube-note youtube-output"><MonitorPlay size={16} />{t.youtubeOutput}</p>
  </article>;
}
