package dev.kyrion.core.integration

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.time.Instant
import java.util.UUID

class IntegrationCatalogTest {
    @Test
    fun `provider metadata distinguishes locality and lifecycle`() {
        val providers = listOf(
            IntegrationProvider("spotify", "Spotify", "", IntegrationLocality.CLOUD, IntegrationAuthType.OAUTH, ProviderAvailability.LIVE, listOf(IntegrationCapability("media.playback", "", ""))),
            IntegrationProvider("google", "Google", "", IntegrationLocality.CLOUD, IntegrationAuthType.OAUTH, ProviderAvailability.PLANNED, emptyList()),
            IntegrationProvider("nanoleaf", "Nanoleaf", "", IntegrationLocality.LOCAL, IntegrationAuthType.LOCAL_DISCOVERY, ProviderAvailability.LIVE, emptyList()),
        )
        assertEquals(IntegrationLocality.CLOUD, providers[0].locality)
        assertEquals(ProviderAvailability.PLANNED, providers[1].availability)
        assertEquals(IntegrationLocality.LOCAL, providers[2].locality)
    }

    @Test
    fun `connection summary serializes only safe metadata`() {
        val summary = IntegrationConnectionSummary("spotify", UUID.randomUUID(), ConnectionStatus.CONNECTED, "user@example.com", listOf("media.playback"), listOf("media.playback"), Instant.now(), Instant.now())
        val json = jacksonObjectMapper().writeValueAsString(summary.copy(createdAt = Instant.EPOCH, updatedAt = Instant.EPOCH).let { mapOf("providerId" to it.providerId, "displayIdentity" to it.displayIdentity, "enabledCapabilities" to it.enabledCapabilities, "status" to it.status) })
        assertTrue(json.contains("user@example.com"))
        listOf("accessToken", "refreshToken", "clientSecret", "apiKey", "credentialCiphertext", "credentialNonce").forEach { assertFalse(json.contains(it)) }
    }
}
