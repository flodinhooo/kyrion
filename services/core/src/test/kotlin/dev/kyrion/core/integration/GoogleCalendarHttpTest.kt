package dev.kyrion.core.integration

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.mockito.Mockito.*
import org.mockito.ArgumentMatchers
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse

class GoogleCalendarHttpTest {
    private val requests = mutableListOf<HttpRequest>()
    private fun client(vararg payloads: Pair<Int,String>): HttpGoogleOAuthClient {
        val http = mock(HttpClient::class.java)
        val queue = ArrayDeque(payloads.toList())
        doAnswer { invocation ->
            requests += invocation.getArgument<HttpRequest>(0)
            val (status, body) = queue.removeFirst()
            @Suppress("UNCHECKED_CAST")
            val response = mock(HttpResponse::class.java) as HttpResponse<String>
            `when`(response.statusCode()).thenReturn(status)
            `when`(response.body()).thenReturn(body)
            response
        }.`when`(http).send(ArgumentMatchers.any(HttpRequest::class.java), ArgumentMatchers.any<HttpResponse.BodyHandler<String>>())
        return HttpGoogleOAuthClient(http)
    }

    @Test fun `range reads paginate include past events and retain all day and recurring instance fields`() {
        val client = client(200 to """{"items":[{"id":"past","summary":"Past","start":{"date":"2026-09-01"},"end":{"date":"2026-09-02"},"etag":"v1"}],"nextPageToken":"page2"}""",
            200 to """{"items":[{"id":"recurring_instance","recurringEventId":"series","start":{"dateTime":"2026-09-02T11:00:00+02:00"},"end":{"dateTime":"2026-09-02T12:00:00+02:00"}},{"id":"deleted","status":"cancelled"}]}""")
        val events = client.rangedEvents("secret", "selected@example.com", "2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z")
        assertEquals(2, events.items.size)
        assertEquals("2026-09-01", events.items[0].start)
        assertTrue(events.items[1].recurring)
        assertTrue(requests[0].uri().path.contains("selected@example.com"))
        assertTrue(requests[0].uri().query.contains("timeMin=2026-09-01"))
        assertTrue(requests[1].uri().query.contains("pageToken=page2"))
    }

    @Test fun `OAuth completion gets account identity from authenticated userinfo`() {
        val client = client(200 to """{"access_token":"secret","refresh_token":"refresh","expires_in":3600}""",
            200 to """{"sub":"12345","email":"owner@example.com","email_verified":true}""")
        assertEquals("owner@example.com", client.exchange("code", "http://localhost.test/callback", "client", "secret").accountName)
        assertEquals("openidconnect.googleapis.com", requests.last().uri().host)
    }

    @Test fun `calendar selection includes all pages and write access metadata`() {
        val client = client(200 to """{"items":[{"id":"first","summary":"First","accessRole":"reader","primary":true}],"nextPageToken":"next"}""",
            200 to """{"items":[{"id":"second","summary":"Second","accessRole":"writer"}]}""")
        val calendars = client.calendars("secret").items
        assertEquals(listOf("first","second"), calendars.map { it.id })
        assertTrue(calendars.first().primary)
        assertEquals("writer", calendars.last().accessRole)
        assertTrue(requests.last().uri().query.contains("pageToken=next"))
    }

    @Test fun `conditional patch and delete use selected calendar instead of primary`() {
        val client = client(200 to """{"id":"event","etag":"v2"}""", 204 to "")
        client.patchEvent("secret", "event", GoogleCalendarEventRequest("selected", "Name", "2026-10-19T09:00:00Z", "2026-10-19T10:00:00Z"), "v1")
        client.removeEvent("secret", "selected", "event", "v2")
        assertEquals(listOf("PATCH", "DELETE"), requests.map { it.method() })
        assertTrue(requests.all { it.uri().path.endsWith("/calendars/selected/events/event") })
        assertEquals("v1", requests[0].headers().firstValue("If-Match").orElseThrow())
        assertEquals("v2", requests[1].headers().firstValue("If-Match").orElseThrow())
    }

    @Test fun `provider precondition failures are preserved for conflict handling`() {
        val client = client(412 to "")
        assertEquals(412, assertThrows<GoogleProviderException> {
            client.removeEvent("secret", "selected", "event", "v1")
        }.status)
    }
}
