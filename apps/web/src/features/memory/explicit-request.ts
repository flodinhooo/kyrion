export function explicitMemoryStatement(content: string, locale: "de" | "en"): string | null {
  const match = locale === "de"
    ? content.match(/^(?:bitte\s+)?merke dir(?:\s+das)?\s*[:,]?\s+(.+)/i)
    : content.match(/^(?:please\s+)?remember(?:\s+this)?\s*[:,]?\s+(.+)/i);
  return match?.[1]?.trim() || null;
}
