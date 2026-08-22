export type ActiveSession = {
  id: string;
  createdAt: string;
  lastSeenAt: string;
  expiresAt: string;
  current: boolean;
};

export function isActiveSession(value: unknown): value is ActiveSession {
  if (!value || typeof value !== "object") return false;
  const session = value as Partial<ActiveSession>;
  return typeof session.id === "string"
    && typeof session.createdAt === "string"
    && typeof session.lastSeenAt === "string"
    && typeof session.expiresAt === "string"
    && typeof session.current === "boolean";
}

export function isActiveSessionList(value: unknown): value is ActiveSession[] {
  return Array.isArray(value) && value.every(isActiveSession);
}
