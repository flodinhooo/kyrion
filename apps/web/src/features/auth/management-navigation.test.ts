import { describe, expect, it } from "vitest";
import { canViewManagementNavigation } from "./management-navigation";

describe("management header navigation", () => {
  it("shows all links for effective owner permissions", () => {
    expect(canViewManagementNavigation([], "users", ["OWNER"])).toBe(true);
    expect(canViewManagementNavigation([], "roles", ["OWNER"])).toBe(true);
    expect(canViewManagementNavigation([], "permissions", ["OWNER"])).toBe(true);
  });

  it("hides each link when its required permission is absent", () => {
    expect(canViewManagementNavigation(["roles:read"], "users")).toBe(false);
    expect(canViewManagementNavigation(["users:read"], "roles")).toBe(false);
    expect(canViewManagementNavigation([], "permissions")).toBe(false);
  });
});
