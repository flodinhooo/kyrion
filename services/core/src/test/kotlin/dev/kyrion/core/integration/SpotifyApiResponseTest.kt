package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.ObjectMapper
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class SpotifyApiResponseTest {
    private val mapper = ObjectMapper()
    @Test
    fun `empty successful player command responses are accepted`() {
        for (status in listOf(200, 202, 204)) {
            assertTrue(spotifyApiResponse(mapper, status, "", false).isObject)
        }
    }
    @Test
    fun `empty or malformed state reads are not reported as successful playback`() {
        assertThrows<SpotifyInvalidResponseException> { spotifyApiResponse(mapper, 200, "", true) }
        assertThrows<SpotifyInvalidResponseException> { spotifyApiResponse(mapper, 200, "not-json", true) }
        assertTrue(spotifyApiResponse(mapper, 204, "", true).isObject)
        assertTrue(spotifyApiResponse(mapper, 200, "{\"is_playing\":true}", true).path("is_playing").asBoolean())
    }
    @Test
    fun `provider errors remain errors regardless of response body`() {
        assertEquals(429, assertThrows<SpotifyProviderException> { spotifyApiResponse(mapper, 429, "", false) }.providerStatus)
    }
}
