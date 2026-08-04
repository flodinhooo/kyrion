package dev.kyrion.core.integration

import java.time.Instant
import java.util.UUID

data class IntegrationConnection(
    val id: UUID,
    val ownerId: UUID,
    val provider: String,
    val displayName: String,
    val endpointHost: String,
    val credentialCiphertext: ByteArray,
    val credentialNonce: ByteArray,
    val credentialVersion: Int,
    val createdAt: Instant,
    val updatedAt: Instant,
)

data class IntegrationConnectionView(
    val id: UUID,
    val provider: String,
    val displayName: String,
    val endpointHost: String,
    val createdAt: Instant,
)

fun IntegrationConnection.view() = IntegrationConnectionView(id, provider, displayName, endpointHost, createdAt)
