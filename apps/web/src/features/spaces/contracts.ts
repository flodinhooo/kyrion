export type Space = { id: string; type: "HOME" | "BUSINESS"; name: string; status: string; defaultRoleKey: string };
export type Invitation = { id: string; createdBy: string; createdAt: string; expiresAt: string; roleKey: string; maxUses: number; useCount: number; status: "ACTIVE" | "REVOKED" | "USED" | "EXPIRED" };
export type IssuedInvitation = { id: string; code: string; expiresAt: string; roleKey: string; maxUses: number };
export function isSpace(value: unknown): value is Space {
  if (!value || typeof value !== "object") return false;
  return "id" in value && typeof value.id === "string" && "name" in value && typeof value.name === "string"
    && "type" in value && (value.type === "HOME" || value.type === "BUSINESS")
    && "defaultRoleKey" in value && typeof value.defaultRoleKey === "string"
    && "status" in value && typeof value.status === "string";
}
export function isInvitation(value: unknown): value is Invitation {
  if (!value || typeof value !== "object") return false;
  return "id" in value && typeof value.id === "string" && "roleKey" in value && typeof value.roleKey === "string"
    && "createdBy" in value && typeof value.createdBy === "string" && "createdAt" in value && typeof value.createdAt === "string"
    && "expiresAt" in value && typeof value.expiresAt === "string" && Number.isFinite(Date.parse(value.expiresAt))
    && "maxUses" in value && Number.isInteger(value.maxUses) && "useCount" in value && Number.isInteger(value.useCount)
    && "status" in value && ["ACTIVE", "REVOKED", "USED", "EXPIRED"].includes(String(value.status));
}
