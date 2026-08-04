package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.ObjectMapper
import org.springframework.stereotype.Component
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration

data class NanoleafDeviceState(val name: String, val model: String?, val serialNumber: String?, val on: Boolean, val brightness: Int?)
data class NanoleafScenes(val active: String?, val items: List<String>, val previews: Map<String, List<String>> = emptyMap())

interface NanoleafGateway {
    fun pair(host: String): String
    fun state(host: String, token: String): NanoleafDeviceState
    fun setPower(host: String, token: String, on: Boolean)
    fun setBrightness(host: String, token: String, brightness: Int)
    fun scenes(host: String, token: String): NanoleafScenes
    fun selectScene(host: String, token: String, name: String)
}

@Component
class NanoleafClient : NanoleafGateway {
    private val objectMapper = ObjectMapper()
    private val client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build()

    override fun pair(host: String): String {
        val response = send(host, "/api/v1/new", "POST")
        if (response.statusCode() == 403) throw NanoleafPairingWindowClosedException()
        if (response.statusCode() !in 200..299) throw NanoleafUnavailableException()
        return objectMapper.readTree(response.body()).path("auth_token").asText().takeIf(String::isNotBlank)
            ?: throw NanoleafInvalidResponseException()
    }

    override fun state(host: String, token: String): NanoleafDeviceState {
        val response = send(host, "/api/v1/$token", "GET")
        if (response.statusCode() !in 200..299) throw NanoleafUnavailableException()
        val root = objectMapper.readTree(response.body())
        return NanoleafDeviceState(
            root.path("name").asText("Nanoleaf"), root.path("model").asText(null), root.path("serialNo").asText(null),
            root.path("state").path("on").path("value").asBoolean(false),
            root.path("state").path("brightness").path("value").takeUnless { it.isMissingNode }?.asInt(),
        )
    }

    override fun setPower(host: String, token: String, on: Boolean) {
        val response = send(host, "/api/v1/$token/state", "PUT", "{\"on\":{\"value\":$on}}")
        if (response.statusCode() !in 200..299) throw NanoleafUnavailableException()
    }

    override fun setBrightness(host: String, token: String, brightness: Int) {
        val response = send(host, "/api/v1/$token/state", "PUT", "{\"brightness\":{\"value\":$brightness}}")
        if (response.statusCode() !in 200..299) throw NanoleafUnavailableException()
    }

    override fun scenes(host: String, token: String): NanoleafScenes {
        val listResponse = send(host, "/api/v1/$token/effects/effectsList", "GET")
        val activeResponse = send(host, "/api/v1/$token/effects/select", "GET")
        if (listResponse.statusCode() !in 200..299 || activeResponse.statusCode() !in 200..299) throw NanoleafUnavailableException()
        val listNode = objectMapper.readTree(listResponse.body())
        val items = if (listNode.isArray) listNode.mapNotNull { it.asText().takeIf(String::isNotBlank) } else emptyList()
        val activeNode = objectMapper.readTree(activeResponse.body())
        val active = when {
            activeNode.isTextual -> activeNode.asText()
            activeNode.path("value").isTextual -> activeNode.path("value").asText()
            activeNode.path("select").isTextual -> activeNode.path("select").asText()
            else -> null
        }
        return NanoleafScenes(active?.takeIf(String::isNotBlank), items.distinct(), effectPreviews(host, token))
    }

    override fun selectScene(host: String, token: String, name: String) {
        val body = objectMapper.writeValueAsString(mapOf("select" to name))
        val response = send(host, "/api/v1/$token/effects", "PUT", body)
        if (response.statusCode() !in 200..299) throw NanoleafUnavailableException()
    }

    private fun effectPreviews(host: String, token: String): Map<String, List<String>> = try {
        val response = send(host, "/api/v1/$token/effects", "PUT", "{\"write\":{\"command\":\"requestAll\"}}")
        if (response.statusCode() !in 200..299 || response.body().isBlank()) return emptyMap()
        objectMapper.readTree(response.body()).path("animations").associate { animation ->
            val name = animation.path("animName").asText()
            val hex = animation.path("hexPalette").takeIf { it.isArray }?.map { "#${it.asText().removePrefix("#")}" }.orEmpty()
            val hsb = animation.path("palette").takeIf { it.isArray }?.map { color ->
                hsvToHex(color.path("hue").asDouble(), color.path("saturation").asDouble(), color.path("brightness").asDouble())
            }.orEmpty()
            name to (hex + hsb).distinct().take(6)
        }.filterKeys(String::isNotBlank).filterValues(List<String>::isNotEmpty)
    } catch (_: Exception) { emptyMap() }

    private fun hsvToHex(hue: Double, saturation: Double, brightness: Double): String {
        val h = ((hue % 360) + 360) % 360 / 60.0; val s = (saturation / 100).coerceIn(0.0, 1.0); val v = (brightness / 100).coerceIn(0.0, 1.0)
        val c = v * s; val x = c * (1 - kotlin.math.abs(h % 2 - 1)); val m = v - c
        val (r, g, b) = when (h.toInt()) { 0 -> Triple(c,x,0.0); 1 -> Triple(x,c,0.0); 2 -> Triple(0.0,c,x); 3 -> Triple(0.0,x,c); 4 -> Triple(x,0.0,c); else -> Triple(c,0.0,x) }
        return "#%02X%02X%02X".format(((r+m)*255).toInt(), ((g+m)*255).toInt(), ((b+m)*255).toInt())
    }

    private fun send(host: String, path: String, method: String, body: String? = null): HttpResponse<String> {
        val builder = HttpRequest.newBuilder(URI("http://$host:16021$path")).timeout(Duration.ofSeconds(5))
        if (body != null) builder.header("Content-Type", "application/json")
        val request = builder.method(method, body?.let(HttpRequest.BodyPublishers::ofString) ?: HttpRequest.BodyPublishers.noBody()).build()
        return try { client.send(request, HttpResponse.BodyHandlers.ofString()) } catch (_: Exception) { throw NanoleafUnavailableException() }
    }
}

class NanoleafPairingWindowClosedException : RuntimeException()
class NanoleafUnavailableException : RuntimeException()
class NanoleafInvalidResponseException : RuntimeException()
