export type YouTubeSource = "VIDEO" | "MUSIC";
export type YouTubeEmbed = { embedUrl: string; watchUrl: string };

export function isYouTubeRequest(value: unknown): value is { url: string; source: YouTubeSource } {
  return !!value && typeof value === "object" && "url" in value && typeof value.url === "string"
    && value.url.trim().length > 0 && value.url.length <= 2048 && "source" in value
    && (value.source === "VIDEO" || value.source === "MUSIC");
}

export function isYouTubeEmbed(value: unknown): value is YouTubeEmbed {
  if (!value || typeof value !== "object" || !("embedUrl" in value) || !("watchUrl" in value)
    || typeof value.embedUrl !== "string" || typeof value.watchUrl !== "string") return false;
  try {
    const embed = new URL(value.embedUrl);
    const watch = new URL(value.watchUrl);
    return embed.protocol === "https:" && embed.hostname === "www.youtube-nocookie.com"
      && !embed.username && !embed.password && !embed.port && /^\/embed\/(?:[A-Za-z0-9_-]{11}|videoseries)$/.test(embed.pathname)
      && watch.protocol === "https:" && ["www.youtube.com", "music.youtube.com"].includes(watch.hostname)
      && !watch.username && !watch.password && !watch.port && ["/watch", "/playlist"].includes(watch.pathname);
  } catch { return false; }
}
