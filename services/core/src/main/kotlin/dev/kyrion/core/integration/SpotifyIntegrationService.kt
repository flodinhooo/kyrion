package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.*
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Service
import java.net.URLEncoder
import java.net.URI
import java.nio.charset.StandardCharsets
import java.security.SecureRandom
import java.time.Clock
import java.time.Instant
import java.util.Base64
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

data class SpotifyStatus(val configured: Boolean, val connected: Boolean, val accountName: String? = null)
data class SpotifyAuthorization(val authorizationUrl: String)
data class SpotifyCredential(val accessToken: String, val refreshToken: String, val expiresAtEpochSecond: Long, val scope: String, val accountName: String)
private data class PendingSpotifyAuthorization(val ownerId: UUID, val expiresAt: Instant)

@Service
class SpotifyIntegrationService(
    private val repository: IntegrationConnectionRepository,
    private val cipher: CredentialCipher,
    private val gateway: SpotifyGateway,
    private val activity: ActivityService,
    @Value("\${kyrion.spotify.client-id:}") private val clientId: String,
    @Value("\${kyrion.spotify.client-secret:}") private val clientSecret: String,
    @Value("\${kyrion.spotify.redirect-uri:}") private val redirectUri: String,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val mapper: ObjectMapper = jacksonObjectMapper()
    private val random = SecureRandom()
    private val pending = ConcurrentHashMap<String, PendingSpotifyAuthorization>()

    fun status(ownerId: UUID): SpotifyStatus {
        val connection = connection(ownerId)
        val account = connection?.let { runCatching { credential(it).accountName }.getOrNull() }
        return SpotifyStatus(configured(), connection != null, account)
    }

    fun authorize(ownerId: UUID): SpotifyAuthorization {
        if (!configured()) throw SpotifyNotConfiguredException()
        val state = ByteArray(32).also(random::nextBytes).let { Base64.getUrlEncoder().withoutPadding().encodeToString(it) }
        pending.entries.removeIf { it.value.expiresAt.isBefore(clock.instant()) }
        pending[state] = PendingSpotifyAuthorization(ownerId, clock.instant().plusSeconds(600))
        val scopes = "user-read-playback-state user-modify-playback-state"
        val url = "https://accounts.spotify.com/authorize?response_type=code&client_id=${enc(clientId)}&scope=${enc(scopes)}&redirect_uri=${enc(redirectUri)}&state=${enc(state)}"
        return SpotifyAuthorization(url)
    }

    fun complete(ownerId: UUID, code: String, state: String): SpotifyStatus {
        val authorization = pending[state]
        if (authorization == null || authorization.ownerId != ownerId || authorization.expiresAt.isBefore(clock.instant())) throw SpotifyInvalidStateException()
        pending.remove(state, authorization)
        val tokens = gateway.exchangeCode(code, redirectUri)
        val profile = gateway.profile(tokens.accessToken)
        val existing = connection(ownerId)
        if (existing != null) repository.delete(ownerId, existing.id)
        val id = UUID.randomUUID(); val now = clock.instant()
        val json = mapper.writeValueAsString(SpotifyCredential(tokens.accessToken, tokens.refreshToken, now.plusSeconds(tokens.expiresIn).epochSecond, tokens.scope, profile.displayName))
        val protected = cipher.protect(json, "$ownerId:$id:spotify")
        repository.save(IntegrationConnection(id, ownerId, "spotify", profile.displayName, profile.id, protected.ciphertext, protected.nonce, protected.version, now, now))
        activity.record(ActivityCategory.INTEGRATION, "spotify.connected", ActivityStatus.SUCCEEDED, ActivityActorType.USER, "spotify", "SPOTIFY_CONNECTED", ownerId.toString(), ownerId = ownerId)
        return SpotifyStatus(true, true, profile.displayName)
    }

    fun devices(ownerId: UUID): List<SpotifyDevice> = withAccessToken(ownerId, gateway::devices)

    fun playback(ownerId: UUID): SpotifyPlayback = withAccessToken(ownerId, gateway::playback)

    fun control(ownerId: UUID, command: SpotifyPlaybackCommand) {
        if (command.deviceId.isBlank() || command.deviceId.length > 200 ||
            (command.action == SpotifyPlaybackAction.VOLUME && command.volumePercent !in 0..100) ||
            (command.action != SpotifyPlaybackAction.VOLUME && command.volumePercent != null)) throw SpotifyInvalidRequestException()
        val correlationId = UUID.randomUUID()
        try {
            withAccessToken(ownerId) { token ->
                val device = gateway.devices(token).firstOrNull { it.id == command.deviceId }
                    ?: throw SpotifyInvalidRequestException()
                if (device.restricted || (command.action == SpotifyPlaybackAction.VOLUME && !device.supportsVolume)) throw SpotifyInvalidRequestException()
                gateway.control(token, command)
            }
        } catch (error: RuntimeException) {
            activity.record(ActivityCategory.CAPABILITY, "media.playback.${command.action.name.lowercase()}", ActivityStatus.FAILED, ActivityActorType.USER, "spotify", "SPOTIFY_PLAYBACK_FAILED", ownerId.toString(), ownerId = ownerId, correlationId = correlationId)
            throw error
        }
        activity.record(ActivityCategory.CAPABILITY, "media.playback.${command.action.name.lowercase()}", ActivityStatus.SUCCEEDED, ActivityActorType.USER, "spotify", "SPOTIFY_PLAYBACK_CONTROLLED", ownerId.toString(), ownerId = ownerId, correlationId = correlationId)
    }

    fun transfer(ownerId: UUID, deviceId: String, play: Boolean) {
        if (deviceId.isBlank() || deviceId.length > 200) throw SpotifyInvalidRequestException()
        withAccessToken(ownerId) { gateway.transfer(it, deviceId, play) }
        activity.record(ActivityCategory.CAPABILITY, "media.playback.transferred", ActivityStatus.SUCCEEDED, ActivityActorType.USER, "spotify", "SPOTIFY_PLAYBACK_TRANSFERRED", ownerId.toString(), ownerId = ownerId)
    }

    fun disconnect(ownerId: UUID) {
        val current = connection(ownerId) ?: throw IntegrationNotFoundException()
        repository.delete(ownerId, current.id)
        activity.record(ActivityCategory.INTEGRATION, "spotify.disconnected", ActivityStatus.SUCCEEDED, ActivityActorType.USER, "spotify", "SPOTIFY_DISCONNECTED", ownerId.toString(), ownerId = ownerId)
    }

    private fun <T> withAccessToken(ownerId: UUID, action: (String) -> T): T {
        val connection = connection(ownerId) ?: throw IntegrationNotFoundException()
        var credential = credential(connection)
        if (credential.expiresAtEpochSecond <= clock.instant().plusSeconds(30).epochSecond) {
            val refreshed = gateway.refresh(credential.refreshToken)
            credential = credential.copy(accessToken = refreshed.accessToken, refreshToken = refreshed.refreshToken, expiresAtEpochSecond = clock.instant().plusSeconds(refreshed.expiresIn).epochSecond, scope = refreshed.scope)
            repository.updateCredential(ownerId, connection.id, cipher.protect(mapper.writeValueAsString(credential), "$ownerId:${connection.id}:spotify"), clock.instant())
        }
        return action(credential.accessToken)
    }

    private fun connection(ownerId: UUID) = repository.findAll(ownerId).firstOrNull { it.provider == "spotify" }
    private fun credential(connection: IntegrationConnection) = mapper.readValue(cipher.reveal(connection), SpotifyCredential::class.java)
    private fun configured(): Boolean {
        if (clientId.isBlank() || clientSecret.isBlank()) return false
        val uri = runCatching { URI(redirectUri) }.getOrNull() ?: return false
        if (uri.host.isNullOrBlank() || uri.userInfo != null || uri.fragment != null || uri.host.equals("localhost", ignoreCase = true)) return false
        return uri.scheme == "https" || (uri.scheme == "http" && uri.host in setOf("127.0.0.1", "[::1]"))
    }
    private fun enc(value: String) = URLEncoder.encode(value, StandardCharsets.UTF_8)
}

class SpotifyInvalidStateException : RuntimeException()
class SpotifyInvalidRequestException : RuntimeException()
