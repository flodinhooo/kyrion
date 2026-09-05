"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ListMusic, Play, RefreshCw } from "lucide-react";
import { useWorkspace } from "@/components/app-shell";
import { isSpotifyPlaylists, type SpotifyPlaylists } from "./contracts";

export function SpotifyPlaylistShelf({ disabled, onPlay }: { disabled: boolean; onPlay: (id: string) => void }) {
  const { t } = useWorkspace();
  const [value, setValue] = useState<SpotifyPlaylists | null>(null);
  const [error, setError] = useState<"unavailable" | "core" | null>(null);
  const [version, setVersion] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch("/api/integrations/spotify/playlists", { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) });
        const body: unknown = await response.json();
        if (response.status === 404) { if (!controller.signal.aborted) setError("core"); return; }
        if (!response.ok || !isSpotifyPlaylists(body)) throw new Error();
        if (!controller.signal.aborted) { setValue(body); setError(null); }
      } catch { if (!controller.signal.aborted) setError("unavailable"); }
    }
    void load();
    return () => controller.abort();
  }, [version]);
  return <section className="spotify-playlists">
    <div className="spotify-playlists-heading"><div><h3>{t.spotifyPlaylistsTitle}</h3><p>{t.spotifyPlaylistsHint}</p></div><button aria-label={t.loungeRefresh} onClick={() => setVersion((v) => v + 1)}><RefreshCw size={17} /></button></div>
    {error ? <p role="status">{error === "core" ? t.spotifyPlaylistsCoreUpdate : t.spotifyPlaylistsError}</p> : !value ? <p role="status">{t.spotifyPlaylistsLoading}</p> : value.reauthorizationRequired ? <div className="spotify-playlists-connect"><p>{t.spotifyPlaylistsPermission}</p><Link href="/plugins/spotify">{t.spotifyRenewAccess} →</Link></div> : value.items.length === 0 ? <p>{t.spotifyPlaylistsEmpty}</p> : <div className="spotify-playlist-grid">{value.items.map((playlist) => <article key={playlist.id}>
      <a href={playlist.url} target="_blank" rel="noreferrer" className="spotify-playlist-info">{playlist.imageUrl ? <Image unoptimized src={playlist.imageUrl} alt="" width={80} height={80} /> : <ListMusic size={40} />}<span>{playlist.name}</span></a>
      <button disabled={disabled} onClick={() => onPlay(playlist.id)} aria-label={`${t.spotifyStartPlaylist}: ${playlist.name}`}><Play size={17} />{t.spotifyStartPlaylist}</button>
    </article>)}</div>}
  </section>;
}
