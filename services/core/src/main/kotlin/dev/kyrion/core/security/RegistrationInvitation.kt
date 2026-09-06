package dev.kyrion.core.security

import java.time.Instant
import java.util.UUID

data class RegistrationInvitation(
    val tokenHash: String,
    val createdBy: UUID,
    val workspaceOwnerId: UUID,
    val expiresAt: Instant,
)

data class CreatedInvitation(val code: String, val expiresAt: Instant)
