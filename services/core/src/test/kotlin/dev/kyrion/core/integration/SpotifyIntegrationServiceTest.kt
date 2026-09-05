package dev.kyrion.core.integration

import dev.kyrion.core.activity.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.io.TempDir
import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets
import java.nio.file.Path
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

class SpotifyIntegrationServiceTest {
    @TempDir lateinit var temp: Path
    private val ownerId = UUID.randomUUID()
    private val events = mutableListOf<ActivityEvent>()

    @Test
    fun `playback commands are owner scoped validated and audited`() {
        val gateway = FakeSpotifyGateway()
        val service = service(SpotifyConnections(), gateway, "client-id", "https://kyrion-node.local/api/integrations/spotify/callback")
        service.complete(ownerId, "code", query(service.authorize(ownerId).authorizationUrl, "state"))
        assertFalse(service.playback(ownerId).playing)
        assertThrows<IntegrationNotFoundException> { service.control(UUID.randomUUID(), SpotifyPlaybackCommand(SpotifyPlaybackAction.RESUME, "device-1")) }
        assertNull(gateway.command)
        assertThrows<SpotifyInvalidRequestException> { service.control(ownerId, SpotifyPlaybackCommand(SpotifyPlaybackAction.VOLUME, "device-1", 101)) }
        assertThrows<SpotifyInvalidRequestException> { service.control(ownerId, SpotifyPlaybackCommand(SpotifyPlaybackAction.VOLUME, "device-1")) }
        assertThrows<SpotifyInvalidRequestException> { service.control(ownerId, SpotifyPlaybackCommand(SpotifyPlaybackAction.PAUSE, "device-1", 50)) }
        assertThrows<SpotifyInvalidRequestException> { service.control(ownerId, SpotifyPlaybackCommand(SpotifyPlaybackAction.RESUME, "missing")) }
        service.control(ownerId, SpotifyPlaybackCommand(SpotifyPlaybackAction.VOLUME, "device-1", 25))
        assertEquals(25, gateway.command?.volumePercent)
        assertEquals("SPOTIFY_PLAYBACK_CONTROLLED", events.last().summaryCode)
        assertEquals(ownerId, events.last().ownerId)
        assertEquals(ActivityStatus.SUCCEEDED, events.last().status)
    }

    @Test
    fun `restricted devices and unsupported volume never reach player control`() {
        val gateway = FakeSpotifyGateway()
        val service = service(SpotifyConnections(), gateway, "client-id", "https://kyrion-node.local/api/integrations/spotify/callback")
        service.complete(ownerId, "code", query(service.authorize(ownerId).authorizationUrl, "state"))
        gateway.restricted = true
        assertThrows<SpotifyInvalidRequestException> { service.control(ownerId, SpotifyPlaybackCommand(SpotifyPlaybackAction.RESUME, "device-1")) }
        gateway.restricted = false
        gateway.supportsVolume = false
        assertThrows<SpotifyInvalidRequestException> { service.control(ownerId, SpotifyPlaybackCommand(SpotifyPlaybackAction.VOLUME, "device-1", 30)) }
        assertNull(gateway.command)
        assertEquals(ActivityStatus.FAILED, events.last().status)
    }

    @Test
    fun `provider failure is recorded without a success event`() {
        val gateway = FakeSpotifyGateway()
        val service = service(SpotifyConnections(), gateway, "client-id", "https://kyrion-node.local/api/integrations/spotify/callback")
        service.complete(ownerId, "code", query(service.authorize(ownerId).authorizationUrl, "state"))
        gateway.failControl = true
        assertThrows<SpotifyUnavailableException> { service.control(ownerId, SpotifyPlaybackCommand(SpotifyPlaybackAction.NEXT, "device-1")) }
        assertEquals("SPOTIFY_PLAYBACK_FAILED", events.last().summaryCode)
        assertEquals(ActivityStatus.FAILED, events.last().status)
    }

    @Test
    fun `oauth completion stores encrypted tokens and exposes devices without secrets`() {
        val repository = SpotifyConnections()
        val gateway = FakeSpotifyGateway()
        val service = service(repository, gateway, "client-id", "https://kyrion-node.local/api/integrations/spotify/callback")
        val authorization = service.authorize(ownerId)
        val state = query(authorization.authorizationUrl, "state")

        val status = service.complete(ownerId, "authorization-code", state)

        assertTrue(status.connected)
        assertEquals("Flo", status.accountName)
        assertEquals("Kyrion Wohnzimmer", service.devices(ownerId).single().name)
        val stored = repository.findAll(ownerId).single()
        assertFalse(String(stored.credentialCiphertext).contains("access-secret"))
        assertEquals("authorization-code", gateway.exchangedCode)
    }

    @Test
    fun `oauth state is owner bound and single use`() {
        val service = service(SpotifyConnections(), FakeSpotifyGateway(), "client-id", "https://kyrion-node.local/api/integrations/spotify/callback")
        val state = query(service.authorize(ownerId).authorizationUrl, "state")
        assertThrows<SpotifyInvalidStateException> { service.complete(UUID.randomUUID(), "code", state) }
        service.complete(ownerId, "code", state)
        assertThrows<SpotifyInvalidStateException> { service.complete(ownerId, "code", state) }
    }

    @Test
    fun `authorization stays unavailable until server configuration is complete`() {
        val service = service(SpotifyConnections(), FakeSpotifyGateway(), "", "")
        assertFalse(service.status(ownerId).configured)
        assertThrows<SpotifyNotConfiguredException> { service.authorize(ownerId) }
    }

    private fun service(repository: SpotifyConnections, gateway: FakeSpotifyGateway, clientId: String, redirectUri: String) =
        SpotifyIntegrationService(repository, CredentialCipher(temp.resolve("credential.key").toString()), gateway,
            ActivityService(object : ActivityEventRepository {
                override fun append(event: ActivityEvent) = event.also(events::add)
                override fun findRecent(limit: Int) = emptyList<ActivityEvent>()
            }), clientId, if (clientId.isBlank()) "" else "client-secret", redirectUri,
            Clock.fixed(Instant.parse("2026-09-04T08:00:00Z"), ZoneOffset.UTC))

    private fun query(url: String, key: String) = URI(url).rawQuery.split("&").associate {
        val parts = it.split("=", limit = 2); URLDecoder.decode(parts[0], StandardCharsets.UTF_8) to URLDecoder.decode(parts[1], StandardCharsets.UTF_8)
    }.getValue(key)
}

private class SpotifyConnections : IntegrationConnectionRepository {
    private val values = mutableListOf<IntegrationConnection>()
    override fun findAll(ownerId: UUID) = values.filter { it.ownerId == ownerId }
    override fun find(ownerId: UUID, id: UUID) = values.firstOrNull { it.ownerId == ownerId && it.id == id }
    override fun save(connection: IntegrationConnection) = connection.also(values::add)
    override fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: Instant) = find(ownerId, id)
    override fun updateCredential(ownerId: UUID, id: UUID, credential: ProtectedCredential, updatedAt: Instant): IntegrationConnection? {
        val index = values.indexOfFirst { it.ownerId == ownerId && it.id == id }; if (index < 0) return null
        return values[index].copy(credentialCiphertext = credential.ciphertext, credentialNonce = credential.nonce, credentialVersion = credential.version, updatedAt = updatedAt).also { values[index] = it }
    }
    override fun delete(ownerId: UUID, id: UUID) = values.removeIf { it.ownerId == ownerId && it.id == id }
}

private class FakeSpotifyGateway : SpotifyGateway {
    var command: SpotifyPlaybackCommand? = null
    var restricted = false
    var supportsVolume = true
    var failControl = false
    var exchangedCode: String? = null
    override fun exchangeCode(code: String, redirectUri: String) = SpotifyTokens("access-secret", "refresh-secret", 3600, "scope").also { exchangedCode = code }
    override fun refresh(refreshToken: String) = SpotifyTokens("access-refreshed", refreshToken, 3600, "scope")
    override fun profile(accessToken: String) = SpotifyProfile("spotify-user", "Flo")
    override fun devices(accessToken: String) = listOf(SpotifyDevice("device-1", "Kyrion Wohnzimmer", "Speaker", false, restricted, 50, supportsVolume))
    override fun transfer(accessToken: String, deviceId: String, play: Boolean) = Unit
    override fun playback(accessToken: String) = SpotifyPlayback(false, null, null, null, null, 0, 0, null, emptyList())
    override fun control(accessToken: String, command: SpotifyPlaybackCommand) {
        if (failControl) throw SpotifyUnavailableException()
        this.command = command
    }
}
