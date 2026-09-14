export const permissionResources = ["users", "roles", "permissions", "invitations", "rooms", "devices", "integrations", "gateways", "voice_satellites", "automations", "conversations", "personal_memories", "activity_log", "backups", "system_settings"] as const;
export const permissionOperations = ["CREATE", "READ", "UPDATE", "DELETE", "EXECUTE"] as const;
export type Permission = `${typeof permissionResources[number]}:${Lowercase<typeof permissionOperations[number]>}`;
export type Role = { id: string; key: string; name: string; system: boolean; permissions: string[]; userCount: number };
export type ManagedUser = { id: string; username: string; enabled: boolean; roles: string[]; permissions: string[] };
export function hasPermission(permissions: readonly string[], permission: string) { return permissions.includes(permission); }
export function isRole(value: unknown): value is Role { const v=value as Role; return !!v && typeof v.id === "string" && typeof v.key === "string" && Array.isArray(v.permissions); }
