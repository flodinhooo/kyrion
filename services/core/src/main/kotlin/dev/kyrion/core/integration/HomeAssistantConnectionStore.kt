package dev.kyrion.core.integration

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import org.springframework.stereotype.Service
import java.net.URI
import java.time.Clock
import java.time.Instant
import java.util.UUID

private data class StoredHomeAssistantCredentials(val baseUrl: String, val accessToken: String)

/** Owner-scoped persistence boundary for a single Home Assistant installation. */
@Service
class HomeAssistantConnectionStore(
    private val connections: IntegrationConnectionRepository,
    private val cipher: CredentialCipher,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val mapper = jacksonObjectMapper()

    fun findForOwner(ownerId: UUID): HomeAssistantConnectionConfig? = connections.findAll(ownerId)
        .firstOrNull { it.provider == HOME_ASSISTANT_PROVIDER && it.credentialCiphertext.isNotEmpty() }
        ?.let { mapper.readValue(cipher.reveal(it), StoredHomeAssistantCredentials::class.java) }
        ?.let { HomeAssistantConnectionConfig(it.baseUrl, it.accessToken) }

    fun connectionForOwner(ownerId: UUID): IntegrationConnection? = connections.findAll(ownerId)
        .firstOrNull { it.provider == HOME_ASSISTANT_PROVIDER && it.credentialCiphertext.isNotEmpty() }

    fun deleteForOwner(ownerId: UUID): Boolean = connectionForOwner(ownerId)?.let { connections.delete(ownerId, it.id) } ?: false

    fun saveForOwner(ownerId: UUID, config: HomeAssistantConnectionConfig): IntegrationConnection {
        val endpoint = endpointHost(config.baseUrl)
        val now = clock.instant()
        val existing = connections.findAll(ownerId).firstOrNull {
            it.provider == HOME_ASSISTANT_PROVIDER && it.credentialCiphertext.isNotEmpty() && it.endpointHost == endpoint
        }
        val id = existing?.id ?: UUID.randomUUID()
        val protected = cipher.protect(mapper.writeValueAsString(StoredHomeAssistantCredentials(config.baseUrl, config.accessToken)), "$ownerId:$id:$HOME_ASSISTANT_PROVIDER")
        return if (existing == null) connections.save(IntegrationConnection(id, ownerId, HOME_ASSISTANT_PROVIDER, "Home Assistant", endpoint, protected.ciphertext, protected.nonce, protected.version, now, now))
        else connections.updateCredential(ownerId, id, protected, now) ?: error("Home Assistant connection disappeared")
    }

    companion object {
        fun endpointHost(baseUrl: String): String {
            val uri = URI(baseUrl)
            return uri.host + if (uri.port > 0) ":${uri.port}" else ""
        }
    }
}
