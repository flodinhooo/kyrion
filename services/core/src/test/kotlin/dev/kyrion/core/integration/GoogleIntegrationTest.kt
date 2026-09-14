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
        verify(grants, times(2)).replace(eq(owner), any(UUID::class.java), eq(setOf("calendar.read")), any(Instant::class.java))
        assertFalse(String(repository.findAll(owner).single().credentialCiphertext).contains("access-secret"))
        assertFalse(service.status(owner).toString().contains("access-secret"))
    }

    private fun query(url: String, key: String) = java.net.URI(url).rawQuery!!.split("&").map { it.split("=", limit = 2) }.associate { it[0] to it[1] }.getValue(key)
}

private class FakeGoogleOAuth : GoogleOAuthClient {
    override fun exchange(code: String, redirectUri: String, clientId: String, clientSecret: String) = GoogleToken("access-secret", "refresh-secret", Instant.now(), "account@example.com")
    override fun refresh(refreshToken: String, clientId: String, clientSecret: String, accountName: String) = GoogleToken("access-refreshed", null, Instant.now(), accountName)
    override fun revoke(token: String) = Unit
    override fun events(accessToken: String) = GoogleCalendarEvents(emptyList())
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
