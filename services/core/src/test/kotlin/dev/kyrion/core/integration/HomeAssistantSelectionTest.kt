package dev.kyrion.core.integration

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.mockito.ArgumentMatchers
import org.mockito.Mockito.*
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.util.UUID

class HomeAssistantSelectionTest {
    @Test
    fun `stored selection request accepts omitted credentials with production Jackson generation`() {
        val request = tools.jackson.databind.json.JsonMapper.builder().build().readValue(
            """{"expectedRevision":1,"devices":[]}""", HomeAssistantOnboardRequest::class.java)
        assertNull(request.accessToken)
        assertNull(request.baseUrl)
        assertEquals(1L, request.expectedRevision)
        assertTrue(request.devices.isEmpty())
    }

    private val mapper = jacksonObjectMapper().findAndRegisterModules()
    private val config = HomeAssistantConnectionConfig("http://192.168.1.10:8123", "synthetic-provider-token")
    private val owner = UUID.randomUUID()
    private val deviceId = "a".repeat(32)
    private fun rows() = listOf("light.first", "switch.second", "sensor.temperature").map { entity ->
        mapOf("id" to deviceId, "entity" to entity, "entityName" to entity.substringAfter('.'), "name" to "Fixture device", "area" to "Kitchen",
            "state" to if (entity.startsWith("sensor")) "21" else "off", "class" to if (entity.startsWith("sensor")) "temperature" else null,
            "unit" to "°C", "updated" to "2026-11-11T12:00:00Z")
    }

    private fun inventory() = HomeAssistantClient(HomeAssistantConfiguration("", "", "")).parse(mapper.valueToTree(rows()))
    private fun choice(control: Boolean = false, room: UUID? = null) = HomeAssistantDeviceChoice(
        haSourceKey(owner, config, deviceId), listOf(haSourceKey(owner, config, deviceId, "light.first")), control, room != null, room)

    @Test
    fun `selection uses opaque keys scoped to owner endpoint and current inventory`() {
        val selected = resolveHaChoices(owner, config, inventory(), listOf(choice()), emptySet()).single()
        assertEquals(setOf("light.first"), selected.entities)
        assertFalse(selected.control)
        assertThrows(HomeAssistantException::class.java) { resolveHaChoices(UUID.randomUUID(), config, inventory(), listOf(choice()), emptySet()) }
        assertThrows(HomeAssistantException::class.java) {
            resolveHaChoices(owner, HomeAssistantConnectionConfig("http://192.168.1.11:8123", "other-token"), inventory(), listOf(choice()), emptySet())
        }
    }

    @Test
    fun `selection cannot cross room scope or silently accept duplicates`() {
        assertThrows(HomeAssistantException::class.java) { resolveHaChoices(owner, config, inventory(), listOf(choice(room = UUID.randomUUID())), emptySet()) }
        assertThrows(HomeAssistantException::class.java) { resolveHaChoices(owner, config, inventory(), listOf(choice(), choice()), emptySet()) }
        val room = UUID.randomUUID()
        assertEquals(room, resolveHaChoices(owner, config, inventory(), listOf(choice(room = room)), setOf(room)).single().roomId)
        assertEquals(emptyList<HomeAssistantSelectedDevice>(), resolveHaChoices(owner, config, inventory(), emptyList(), emptySet()))
    }

    @Test
    fun `control consent is explicit and requires one supported power entity`() {
        assertTrue(resolveHaChoices(owner, config, inventory(), listOf(choice(control = true)), emptySet()).single().control)
        val two = choice(true).copy(entityKeys = listOf("light.first", "switch.second").map { haSourceKey(owner, config, deviceId, it) })
        assertThrows(HomeAssistantException::class.java) { resolveHaChoices(owner, config, inventory(), listOf(two), emptySet()) }
        val sensor = choice(true).copy(entityKeys = listOf(haSourceKey(owner, config, deviceId, "sensor.temperature")))
        assertThrows(HomeAssistantException::class.java) { resolveHaChoices(owner, config, inventory(), listOf(sensor), emptySet()) }
    }

    @Suppress("UNCHECKED_CAST") // Erased Mockito response only, never production/provider parsing.
    private fun response(body: String): HttpResponse<InputStream> {
        val response = mock(HttpResponse::class.java) as HttpResponse<InputStream>
        `when`(response.statusCode()).thenReturn(200)
        `when`(response.body()).thenAnswer { ByteArrayInputStream(body.toByteArray()) }
        return response
    }

    @Test
    fun `selected entity aggregation excludes unselected power and sensor states`() {
        val http = mock(HttpClient::class.java)
        val fixtureResponse = response(mapper.writeValueAsString(rows()))
        `when`(http.send(any(HttpRequest::class.java), ArgumentMatchers.any<HttpResponse.BodyHandler<InputStream>>())).thenReturn(fixtureResponse)
        val client = HomeAssistantClient(HomeAssistantConfiguration("", "", ""), mapper, http)
        val selected = client.snapshot(config, mapOf(deviceId to setOf("light.first"))).single()
        assertEquals(false, selected.state.on)
        assertNull(selected.state.temperatureCelsius)
        assertEquals(listOf("light.first"), selected.entities.map { it.id })
        assertTrue(client.snapshot(config, emptyMap()).isEmpty())
    }

    @Test
    fun `power sends one fixed service call and confirms actual provider state`() {
        val http = mock(HttpClient::class.java)
        val requests = mutableListOf<HttpRequest>()
        `when`(http.send(any(HttpRequest::class.java), ArgumentMatchers.any<HttpResponse.BodyHandler<InputStream>>())).thenAnswer { invocation ->
            val request = invocation.getArgument<HttpRequest>(0)
            requests.add(request)
            response(if (request.method() == "POST") "[]" else """{"entity_id":"light.first","state":"on","last_updated":"2026-11-11T12:01:00Z"}""")
        }
        val client = HomeAssistantClient(HomeAssistantConfiguration("", "", ""), mapper, http)
        assertTrue(client.power(config, "light.first", true).on)
        assertEquals(listOf("/api/services/light/turn_on", "/api/states/light.first"), requests.map { it.uri().path })
        assertEquals(listOf("POST", "GET"), requests.map { it.method() })
        assertTrue(requests.all { it.headers().firstValue("Authorization").orElse("") == "Bearer synthetic-provider-token" })
    }

    @Test
    fun `HTTP success without matching state never becomes action success and is not resent`() {
        val http = mock(HttpClient::class.java)
        var posts = 0
        `when`(http.send(any(HttpRequest::class.java), ArgumentMatchers.any<HttpResponse.BodyHandler<InputStream>>())).thenAnswer { invocation ->
            val request = invocation.getArgument<HttpRequest>(0)
            if (request.method() == "POST") posts++
            response(if (request.method() == "POST") "[]" else """{"entity_id":"light.first","state":"off"}""")
        }
        val client = HomeAssistantClient(HomeAssistantConfiguration("", "", ""), mapper, http)
        assertEquals("control_not_confirmed", assertThrows(HomeAssistantException::class.java) { client.power(config, "light.first", true) }.code)
        assertEquals(1, posts)
        assertThrows(HomeAssistantException::class.java) { client.power(config, "script.arbitrary", true) }
        assertThrows(HomeAssistantException::class.java) { client.power(config, "light.first/../../script", true) }
        assertEquals(1, posts)
    }
}
