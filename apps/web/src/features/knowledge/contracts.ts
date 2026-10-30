export type KnowledgeSource = {
  documentId: string; filename: string; excerpt: string; page: number | null;
  startOffset: number; endOffset: number; reference: string;
};

export function isKnowledgeSource(value: unknown): value is KnowledgeSource {
  if (!value || typeof value !== "object") return false;
  const s = value as Partial<KnowledgeSource>;
  return typeof s.documentId === "string" && /^[0-9a-f-]{36}$/.test(s.documentId)
    && typeof s.filename === "string" && s.filename.length <= 200
    && typeof s.excerpt === "string" && s.excerpt.length <= 2000
    && (s.page === null || (typeof s.page === "number" && Number.isInteger(s.page) && s.page > 0))
    && typeof s.startOffset === "number" && Number.isInteger(s.startOffset) && s.startOffset >= 0
    && typeof s.endOffset === "number" && Number.isInteger(s.endOffset) && s.endOffset > s.startOffset
    && typeof s.reference === "string" && new RegExp(`^kd:${s.documentId}:[0-9]+:[0-9]+$`).test(s.reference);
}
