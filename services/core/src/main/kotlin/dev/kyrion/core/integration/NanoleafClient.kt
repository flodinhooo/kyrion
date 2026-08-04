package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.ObjectMapper
import org.springframework.stereotype.Component
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration

data class NanoleafDeviceState(val name: String, val model: String?, val serialNumber: String?, val on: Boolean, val brightness: Int?)

interface NanoleafGateway {
    fun pair(host: String): String
    fun state(host: String, token: String): NanoleafDeviceState
    fun setPower(host: String, token: String, on: Boolean)
    fun setBrightness(host: String, token: String, brightness: Int)
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
