package dev.kyrion.core.integration

import com.fasterxml.jackson.annotation.JsonCreator
import com.fasterxml.jackson.annotation.JsonValue
import java.time.Instant
import java.util.UUID

enum class DeviceClass(@get:JsonValue val value: String) {
    LIGHT("light"), SWITCH("switch"), SENSOR("sensor"), OTHER("other");

    companion object {
        @JvmStatic
        @JsonCreator
        fun fromValue(value: String): DeviceClass = entries.firstOrNull { it.value == value.lowercase() }
            ?: throw IllegalArgumentException("Unsupported device class")
    }
}

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
    val roomId: UUID? = null,
    val deviceClass: DeviceClass = DeviceClass.OTHER,
)

data class IntegrationConnectionView(
    val id: UUID,
    val provider: String,
    val displayName: String,
    val endpointHost: String,
    val createdAt: Instant,
    val roomId: UUID?,
    val deviceClass: String,
)

fun IntegrationConnection.view() = IntegrationConnectionView(id, provider, displayName, endpointHost, createdAt, roomId, deviceClass.value)
