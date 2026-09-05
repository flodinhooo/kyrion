// Preferences must never prevent the platform from working when storage is blocked.
export function readPreference(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}

export function writePreference(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* Keep the in-memory preference. */ }
}
