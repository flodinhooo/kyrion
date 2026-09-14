package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test

class RbacRegistryTest {
    @Test
    fun `registry maps protected feature families to known permissions`() {
        val expected = mapOf(
            "/v1/rbac/roles" to "roles:read",
            "/v1/rbac/users" to "users:read",
            "/v1/activity" to "activity_log:read",
            "/v1/home/rooms" to "rooms:read",
            "/v1/devices" to "devices:read",
            "/v1/device-commands" to "devices:execute",
            "/v1/gateways" to "gateways:read",
            "/v1/integrations" to "integrations:read",
            "/v1/backups" to "backups:read",
        )
        val catalog = setOf("users", "roles", "activity_log", "rooms", "devices", "gateways", "integrations", "backups")
        expected.forEach { (path, permission) ->
            assertThat(permissionFor(path, "GET")).isEqualTo(permission)
            assertThat(permission.substringBefore(':')).isIn(catalog)
        }
    }

    @Test
    fun `registry leaves unsupported methods unmapped instead of granting access`() {
        assertThat(permissionFor("/v1/rbac/roles", "TRACE")).isNull()
        assertThat(permissionFor("/v1/unknown", "GET")).isNull()
    }
}
