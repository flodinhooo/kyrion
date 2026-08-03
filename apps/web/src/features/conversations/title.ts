const MAX_TITLE_LENGTH = 72;

export function createConversationTitle(content: string, locale: "de" | "en"): string {
  const normalized = content.trim().replace(/\s+/g, " ").replace(/^(?:[#>*_`~-]+|\d+[.)])\s*/, "");
  const sentence = normalized.match(/^.*?[.!?](?:\s|$)/)?.[0]?.trim() ?? normalized;
  const shortened = sentence.length <= MAX_TITLE_LENGTH
    ? sentence
    : `${sentence.slice(0, MAX_TITLE_LENGTH - 1).replace(/\s+\S*$/, "").trimEnd()}…`;
  if (!shortened) return locale === "de" ? "Neue Unterhaltung" : "New conversation";
  return shortened[0]!.toLocaleUpperCase(locale) + shortened.slice(1);
}
