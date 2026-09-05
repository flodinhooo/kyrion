package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.ObjectMapper
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration

object NetworkDeviceIdentity {
    private val client = HttpClient.newBuilder().connectTimeout(Duration.ofMillis(500))
        .followRedirects(HttpClient.Redirect.NEVER).build()
    private val mapper = ObjectMapper()

    fun shelly(host: String): DiscoveredNetworkDevice? {
        privateNetworkIpv4(host)
        return try {
            val response = client.send(HttpRequest.newBuilder(URI("http://$host/shelly"))
                .timeout(Duration.ofMillis(1000)).GET().build(), HttpResponse.BodyHandlers.ofString())
            if (response.statusCode() != 200 || response.body().length > 16384) null else parseShelly(host, response.body())
        } catch (_: InterruptedException) { Thread.currentThread().interrupt(); null }
        catch (_: java.io.IOException) { null }
    }

    fun parseShelly(host: String, body: String): DiscoveredNetworkDevice? = try {
        val root = mapper.readTree(body)
        val id = root.path("id").takeIf { it.isTextual }?.asText()?.takeIf { it.startsWith("shelly", true) && it.length <= 160 }
        if (id == null) null else DiscoveredNetworkDevice(NetworkDiscoveryRules.provider("", id), id, host, 80)
    } catch (_: com.fasterxml.jackson.core.JsonProcessingException) { null }
}
