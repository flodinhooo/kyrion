package dev.kyrion.core.integration

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.api.io.TempDir
import org.mockito.Mockito.*
import java.nio.file.Path
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

class GoogleIntegrationTest {
    @TempDir lateinit var temp: Path

    @Test
    fun `state is owner bound single use and reconnect reuses account connection`() {
        val owner = UUID.randomUUID(); val repository = GoogleConnections(); val grants = mock(JdbcIntegrationCapabilityGrantRepository::class.java)
        val oauth = FakeGoogleOAuth(); val service = GoogleIntegrationService(repository, grants, CredentialCipher(temp.resolve("key").toString()), oauth, "client", "secret", "http://localhost:3000/api/integrations/google/callback", Clock.fixed(Instant.parse("2026-09-14T00:00:00Z"), ZoneOffset.UTC))
        val state = query(service.authorize(owner).authorizationUrl, "state")
        assertThrows<GoogleInvalidStateException> { service.complete(UUID.randomUUID(), "code", state) }
        service.complete(owner, "code", state)
        assertThrows<GoogleInvalidStateException> { service.complete(owner, "code", state) }
        service.complete(owner, "code-2", query(service.authorize(owner).authorizationUrl, "state"))
        assertEquals(1, repository.findAll(owner).size)
        assertFalse(String(repository.findAll(owner).single().credentialCiphertext).contains("access-secret"))
        assertFalse(service.status(owner).toString().contains("access-secret"))
    }

    @Test
    fun `expired credentials refresh once and preserve the encrypted refresh token`() {
        val owner = UUID.randomUUID()
        val repository = GoogleConnections()
        val grants = mock(JdbcIntegrationCapabilityGrantRepository::class.java)
        val oauth = FakeGoogleOAuth()
        val service = GoogleIntegrationService(repository, grants, CredentialCipher(temp.resolve("refresh-key").toString()), oauth,
            "client", "secret", "http://localhost.test/callback")
        service.complete(owner, "code", query(service.authorize(owner).authorizationUrl, "state"))
        val connection = repository.findAll(owner).single()
        `when`(grants.findAll(owner, connection.id)).thenReturn(listOf(IntegrationCapabilityGrant(owner, connection.id, "calendar.read", true, Instant.now(), Instant.now())))
        service.events(owner)
        service.events(owner)
        assertEquals(1, oauth.refreshes)
        assertEquals(listOf("access-refreshed", "access-refreshed"), oauth.readTokens)
        assertFalse(String(repository.findAll(owner).single().credentialCiphertext).contains("refresh-secret"))
    }

    @Test
    fun `revoked refresh token reports reauthorization without dropping the connection`() {
        val owner = UUID.randomUUID()
        val repository = GoogleConnections()
        val grants = mock(JdbcIntegrationCapabilityGrantRepository::class.java)
        val oauth = FakeGoogleOAuth().apply { refreshFailure = true }
        val service = GoogleIntegrationService(repository, grants, CredentialCipher(temp.resolve("revoked-key").toString()), oauth,
            "client", "secret", "http://localhost.test/callback")
        service.complete(owner, "code", query(service.authorize(owner).authorizationUrl, "state"))
        val connection = repository.findAll(owner).single()
        `when`(grants.findAll(owner, connection.id)).thenReturn(listOf(IntegrationCapabilityGrant(owner, connection.id, "calendar.read", true, Instant.now(), Instant.now())))
        assertThrows<GoogleReauthorizationException> { service.events(owner) }
        assertTrue(service.status(owner).reauthorizationRequired)
        assertThrows<GoogleReauthorizationException> { service.events(owner) }
        assertEquals(1,oauth.refreshes)
        assertEquals(1, repository.findAll(owner).size)
    }

    @Test
    fun `Core rejects recurring and all day mutations even when the caller bypasses the UI`() {
        val owner=UUID.randomUUID(); val repository=GoogleConnections(); val grants=mock(JdbcIntegrationCapabilityGrantRepository::class.java)
        val oauth=FakeGoogleOAuth()
        val service=GoogleIntegrationService(repository,grants,CredentialCipher(temp.resolve("readonly-key").toString()),oauth,"client","secret","http://localhost.test/callback")
        service.complete(owner,"code",query(service.authorize(owner).authorizationUrl,"state"))
        val connection=repository.findAll(owner).single()
        `when`(grants.findAll(owner,connection.id)).thenReturn(listOf("calendar.read","calendar.event.update","calendar.event.delete").map { IntegrationCapabilityGrant(owner,connection.id,it,true,Instant.now(),Instant.now()) })
        val body=GoogleCalendarEventRequest("selected","Edit","2026-10-19T09:00:00Z","2026-10-19T10:00:00Z",etag="v1")
        oauth.remote=GoogleCalendarEvent("event","Recurring",body.start,body.end,"v1",recurring=true)
        assertThrows<GoogleReadOnlyEventException> { service.updateEvent(owner,"event",body) }
        assertThrows<GoogleReadOnlyEventException> { service.deleteEvent(owner,"event","selected","v1") }
        oauth.remote=oauth.remote!!.copy(recurring=false,start="2026-10-19",end="2026-10-20")
        assertThrows<GoogleReadOnlyEventException> { service.updateEvent(owner,"event",body) }
        assertThrows<GoogleReadOnlyEventException> { service.deleteEvent(owner,"event","selected","v1") }
        assertEquals(0,oauth.writes)
    }

    private fun query(url: String, key: String) = java.net.URI(url).rawQuery!!.split("&").map { it.split("=", limit = 2) }.associate { it[0] to it[1] }.getValue(key)
}

private class FakeGoogleOAuth : GoogleOAuthClient {
    var remote: GoogleCalendarEvent? = null
    var writes = 0
    override fun getEvent(accessToken: String, calendarId: String, eventId: String) = remote!!
    override fun patchEvent(accessToken: String, eventId: String, body: GoogleCalendarEventRequest, etag: String): GoogleCalendarEvent { writes++; return remote!! }
    override fun removeEvent(accessToken: String, calendarId: String, eventId: String, etag: String) { writes++ }
    var refreshes = 0
    var refreshFailure = false
    val readTokens = mutableListOf<String>()
    override fun exchange(code: String, redirectUri: String, clientId: String, clientSecret: String) = GoogleToken("access-secret", "refresh-secret", Instant.now(), "account@example.com")
    override fun refresh(refreshToken: String, clientId: String, clientSecret: String, accountName: String): GoogleToken {
        refreshes++
        if (refreshFailure) throw GoogleProviderException(400)
        return GoogleToken("access-refreshed", null, Instant.now().plusSeconds(3600), accountName)
    }
    override fun revoke(token: String) = Unit
    override fun events(accessToken: String): GoogleCalendarEvents { readTokens += accessToken; return GoogleCalendarEvents(emptyList()) }
}

private class GoogleConnections : IntegrationConnectionRepository {
    private val values = mutableListOf<IntegrationConnection>()
    override fun findAll(ownerId: UUID) = values.filter { it.ownerId == ownerId }
    override fun find(ownerId: UUID, id: UUID) = values.firstOrNull { it.ownerId == ownerId && it.id == id }
    override fun save(connection: IntegrationConnection) = connection.also { values.add(it) }
    override fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: Instant) = find(ownerId, id)
    override fun updateCredential(ownerId: UUID, id: UUID, credential: ProtectedCredential, updatedAt: Instant): IntegrationConnection? {
        val index = values.indexOfFirst { it.ownerId == ownerId && it.id == id }; if (index < 0) return null
        return values[index].copy(credentialCiphertext = credential.ciphertext, credentialNonce = credential.nonce, credentialVersion = credential.version, updatedAt = updatedAt).also { values[index] = it }
    }
    override fun delete(ownerId: UUID, id: UUID) = values.removeIf { it.ownerId == ownerId && it.id == id }
}
