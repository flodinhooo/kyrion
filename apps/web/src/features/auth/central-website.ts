import type { Locale } from "@/lib/messages";

// Official website codes belong only to the official central realm. Keep
// isolated or independently hosted providers on their own verification page.
export function centralWebsite(verificationUri: string, locale: Locale): string | null {
  try {
    const uri = new URL(verificationUri);
    if (uri.origin !== "https://auth.kyrion.ch" || uri.pathname !== "/realms/kyrion/device") return null;
    return `https://www.kyrion.ch${locale === "en" ? "/en" : ""}/connect`;
  } catch { return null; }
}
