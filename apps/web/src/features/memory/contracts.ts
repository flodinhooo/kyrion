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
  active?: boolean;
  expiresAt?: string | null;
  ownerId?: string | null;
};

export type MemoryProfile = {
  settings: {
    enabled: boolean;
    updatedAt: string | null;
    historyEnabled?: boolean;
    preferencesEnabled?: boolean; kyrionDataEnabled?: boolean;
    categories?: MemoryCategory[]
  };
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
    && (item.active === undefined || typeof item.active === "boolean")
    && (item.expiresAt === undefined || item.expiresAt === null || (typeof item.expiresAt === "string" && Number.isFinite(Date.parse(item.expiresAt))))
    && (item.conflictsWithMemoryId === null || typeof item.conflictsWithMemoryId === "string");
}

export function isMemoryProfile(value: unknown): value is MemoryProfile {
  if (!value || typeof value !== "object") return false;
  const profile = value as Partial<MemoryProfile>;
  return !!profile.settings && typeof profile.settings.enabled === "boolean"
    && Array.isArray(profile.items) && profile.items.every(isPersonalMemory);
}

export type ContextSource = {
  kind: string;
  id: string | null;
  privacy: "local_only" | "cloud_current" | "blocked";
  selected: boolean;
  reason: string;
  estimatedTokens: number
};

export function isContextSources(value: unknown): value is ContextSource[] {
  return Array.isArray(value) && value.length <= 100 && value.every(item => item && typeof item === "object"
    && typeof item.kind === "string" && (item.id === null || typeof item.id === "string")
    && ["local_only", "cloud_current", "blocked"].includes(item.privacy) && typeof item.selected === "boolean"
    && typeof item.reason === "string" && Number.isSafeInteger(item.estimatedTokens) && item.estimatedTokens >= 0);
}
