"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Star } from "lucide-react";
import { useWorkspace } from "@/components/app-shell";
import type { Room } from "@/features/home/contracts";
import { MAX_ROOM_FAVORITES, parseRoomFavorites, toggleRoomFavorite } from "@/features/home/favorites";

export function HomeRoomFavorites({ rooms, onOpen }: { rooms: Room[]; onOpen: (id: string) => void }) {
  const { t, username } = useWorkspace();
  const storageKey = `kyrion-room-favorites:${encodeURIComponent(username)}`;
  const [favorites, setFavorites] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  const [storageFailed, setStorageFailed] = useState(false);

  useEffect(() => {
    let disposed = false;
    queueMicrotask(() => {
      if (disposed) return;
      try { setFavorites(parseRoomFavorites(localStorage.getItem(storageKey))); }
      catch { setFavorites([]); setStorageFailed(true); }
      setReady(true);
    });
    return () => { disposed = true; };
  }, [storageKey]);

  const visible = favorites.filter((id) => rooms.some((room) => room.id === id));

  function toggle(id: string) {
    const next = toggleRoomFavorite(visible, id);
    setFavorites(next);
    try { localStorage.setItem(storageKey, JSON.stringify(next)); setStorageFailed(false); }
    catch { setStorageFailed(true); }
  }

  if (!rooms.length || !ready) return null;
  return <section className="home-favorites" aria-labelledby="home-favorites-title">
    <div className="home-section-heading"><div><h2 id="home-favorites-title">{t.homeFavorites}</h2><p>{t.homeFavoritesHint}</p></div></div>
    {visible.length > 0 ? <div className="home-favorite-grid">{visible.map((id) => {
      const room = rooms.find((item) => item.id === id);
      if (!room) return null;
      return <button type="button" key={id} onClick={() => onOpen(id)}><Star aria-hidden="true" /><strong>{room.name}</strong><ArrowRight aria-hidden="true" /></button>;
    })}</div> : <p className="home-favorites-empty">{t.homeFavoritesEmpty}</p>}
    <details className="home-favorites-picker"><summary>{t.homeFavoritesEdit}</summary>
      <div>{rooms.map((room) => <label key={room.id}><input type="checkbox" checked={visible.includes(room.id)} disabled={!visible.includes(room.id) && visible.length >= MAX_ROOM_FAVORITES} onChange={() => toggle(room.id)} /><span>{room.name}</span></label>)}</div>
      <p>{t.homeFavoritesLimit.replace("{count}", String(MAX_ROOM_FAVORITES))}</p>
    </details>
    {storageFailed && <p role="status">{t.homeFavoritesStorageError}</p>}
  </section>;
}
