package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import org.springframework.stereotype.Component
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration

data class ShellySensorReading(val temperatureCelsius: Double?, val relativeHumidity: Double?, val battery: Double?)

interface ShellyGateway {
    fun read(host: String): ShellySensorReading
}

class ShellyException(val code: String) : RuntimeException(code)

object ShellyResponses {
    fun validateDevice(root: JsonNode) {
        if (!root.path("gen").isIntegralNumber || root.path("gen").asInt() !in 2..3 ||
            root.path("app").asText() != "HT") throw ShellyException("SHELLY_UNSUPPORTED_DEVICE")
        if (root.path("auth_en").asBoolean()) throw ShellyException("SHELLY_AUTH_REQUIRED")
    }

    fun reading(root: JsonNode): ShellySensorReading {
        if (!root.path("temperature:0").isObject || !root.path("humidity:0").isObject) {
            throw ShellyException("SHELLY_INVALID_RESPONSE")
        }
        return ShellySensorReading(
            number(root.path("temperature:0").path("tC"), -100.0, 150.0),
            number(root.path("humidity:0").path("rh"), 0.0, 100.0),
            number(root.path("devicepower:0").path("battery").path("percent"), 0.0, 100.0),
        )
    }

    private fun number(node: JsonNode, min: Double, max: Double): Double? {
        if (node.isNull || node.isMissingNode) return null
        if (!node.isNumber || !node.asDouble().isFinite() || node.asDouble() !in min..max) {
            throw ShellyException("SHELLY_INVALID_RESPONSE")
        }
        return node.asDouble()
    }
}

@Component
class ShellyClient : ShellyGateway {
    private val mapper = ObjectMapper()
    private val client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2))
        .followRedirects(HttpClient.Redirect.NEVER).build()

    override fun read(host: String): ShellySensorReading {
        val address = privateNetworkIpv4(host)
        ShellyResponses.validateDevice(get(address, "Shelly.GetDeviceInfo"))
        return ShellyResponses.reading(get(address, "Shelly.GetStatus"))
    }

    private fun get(host: String, method: String): JsonNode = try {
        val request = HttpRequest.newBuilder(URI("http://$host/rpc/$method"))
            .timeout(Duration.ofSeconds(3)).GET().build()
        val response = client.send(request, HttpResponse.BodyHandlers.ofString())
        if (response.statusCode() == 401) throw ShellyException("SHELLY_AUTH_REQUIRED")
        if (response.statusCode() != 200) throw ShellyException("SHELLY_UNAVAILABLE")
        if (response.body().length > 65536) throw ShellyException("SHELLY_INVALID_RESPONSE")
        try { mapper.readTree(response.body()) ?: throw ShellyException("SHELLY_INVALID_RESPONSE") }
        catch (_: com.fasterxml.jackson.core.JsonProcessingException) { throw ShellyException("SHELLY_INVALID_RESPONSE") }
    } catch (exception: ShellyException) {
        throw exception
    } catch (_: InterruptedException) {
        Thread.currentThread().interrupt()
        throw ShellyException("SHELLY_UNAVAILABLE")
    } catch (_: java.io.IOException) {
        throw ShellyException("SHELLY_UNAVAILABLE")
    }
}
