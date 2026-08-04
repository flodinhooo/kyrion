export type MemoryCategory = "preference" | "person" | "project" | "value" | "other";
export type MemorySensitivity = "standard" | "sensitive";
export type MemoryStatus = "proposed" | "confirmed" | "superseded";

export type PersonalMemory = {
  id: string;
  category: MemoryCategory;
  content: string;
  sensitivity: MemorySensitivity;
  origin: "explicit";
  status: MemoryStatus;
  sourceConversationId: string | null;
  sourceMessageId: string | null;
  createdAt: string;
  updatedAt: string;
  confirmedAt: string | null;
  conflictsWithMemoryId: string | null;
};

export type MemoryProfile = {
  settings: { enabled: boolean; updatedAt: string | null };
  items: PersonalMemory[];
};

const categories = new Set(["preference", "person", "project", "value", "other"]);

export function isPersonalMemory(value: unknown): value is PersonalMemory {
  if (!value || typeof value !== "object") return false;
  const item = value as Partial<PersonalMemory>;
  return typeof item.id === "string" && categories.has(item.category ?? "")
    && typeof item.content === "string"
    && (item.sensitivity === "standard" || item.sensitivity === "sensitive")
    && (item.status === "proposed" || item.status === "confirmed" || item.status === "superseded")
    && (item.conflictsWithMemoryId === null || typeof item.conflictsWithMemoryId === "string");
}

export function isMemoryProfile(value: unknown): value is MemoryProfile {
  if (!value || typeof value !== "object") return false;
  const profile = value as Partial<MemoryProfile>;
  return !!profile.settings && typeof profile.settings.enabled === "boolean"
    && Array.isArray(profile.items) && profile.items.every(isPersonalMemory);
}
