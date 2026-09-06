package dev.kyrion.core.integration

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.util.UUID

class HomeAssistantHttpTest {
    @Test
    fun `authentication unreachable and malformed responses become safe diagnostic codes`() {
        val owner = UUID.randomUUID()
        val config = HomeAssistantConfiguration("http://192.168.1.10:8123", "private-token", owner.toString())
        for ((status, body, code) in listOf(
            Triple(401, "private-token", "authentication_failed"),
            Triple(403, "private-token", "authentication_failed"), Triple(200, "not json", "invalid_response"),
            Triple(503, "private-token", "dependency_error")
        )) {
            val http = mock(HttpClient::class.java)

            @Suppress("UNCHECKED_CAST")
            val response = mock(HttpResponse::class.java) as HttpResponse<InputStream>
            `when`(response.statusCode()).thenReturn(status)
            `when`(response.body()).thenReturn(ByteArrayInputStream(body.toByteArray()))
            `when`(
                http.send(
                    any(HttpRequest::class.java),
                    org.mockito.ArgumentMatchers.any<HttpResponse.BodyHandler<InputStream>>()
                )
            ).thenReturn(response)
            val client = HomeAssistantClient(config, jacksonObjectMapper(), http)
            assertEquals(code, assertThrows(HomeAssistantException::class.java) { client.snapshot(owner) }.code)
        }
        val http = mock(HttpClient::class.java)
        `when`(
            http.send(
                any(HttpRequest::class.java),
                org.mockito.ArgumentMatchers.any<HttpResponse.BodyHandler<InputStream>>()
            )
        ).thenThrow(java.io.IOException("private-token"))
        assertEquals("dependency_unreachable", assertThrows(HomeAssistantException::class.java) {
            HomeAssistantClient(config, jacksonObjectMapper(), http).snapshot(owner)
        }.code)
    }
}
