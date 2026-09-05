export const MAX_ROOM_FAVORITES = 8;

export function parseRoomFavorites(raw: string | null): string[] {
  if (!raw || raw.length > 4096) return [];
  try {
    const value: unknown = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return [...new Set(value.filter((id): id is string =>
      typeof id === "string" && /^[a-zA-Z0-9-]{1,128}$/.test(id),
    ))].slice(0, MAX_ROOM_FAVORITES);
  } catch { return []; }
}

export function toggleRoomFavorite(current: string[], id: string): string[] {
  if (current.includes(id)) return current.filter((item) => item !== id);
  return current.length < MAX_ROOM_FAVORITES ? [...current, id] : current;
}
