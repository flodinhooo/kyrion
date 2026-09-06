package dev.kyrion.core.security

import java.time.Instant
import java.util.UUID

data class UserAccount(
    val id: UUID,
    val username: String,
    val passwordHash: String,
    val enabled: Boolean,
    val createdAt: Instant,
    val updatedAt: Instant,
    val workspaceOwnerId: UUID? = null,
) {
    val resourceOwnerId: UUID get() = workspaceOwnerId ?: id
}
