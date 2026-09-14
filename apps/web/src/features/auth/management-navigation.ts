export type ManagementNavigationKey = "users" | "roles" | "permissions";

const requiredPermissions: Record<ManagementNavigationKey, string> = {
  users: "users:read",
  roles: "roles:read",
  permissions: "roles:read",
};

export function canViewManagementNavigation(permissions: readonly string[], item: ManagementNavigationKey, roles: readonly string[] = []): boolean {
  return roles.includes("OWNER") || permissions.includes(requiredPermissions[item]);
}
