package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.ObjectMapper
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.net.URI
import java.net.URLEncoder
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.charset.StandardCharsets
import java.time.Duration
import java.util.Base64

data class SpotifyTokens(val accessToken: String, val refreshToken: String, val expiresIn: Long, val scope: String)
data class SpotifyProfile(val id: String, val displayName: String)
data class SpotifyDevice(val id: String, val name: String, val type: String, val active: Boolean, val restricted: Boolean, val volumePercent: Int?, val supportsVolume: Boolean)

interface SpotifyGateway {
    fun exchangeCode(code: String, redirectUri: String): SpotifyTokens
    fun refresh(refreshToken: String): SpotifyTokens
    fun profile(accessToken: String): SpotifyProfile
    fun devices(accessToken: String): List<SpotifyDevice>
    fun transfer(accessToken: String, deviceId: String, play: Boolean)
}

@Component
class SpotifyClient(
    @Value("\${kyrion.spotify.client-id:}") private val clientId: String,
    @Value("\${kyrion.spotify.client-secret:}") private val clientSecret: String,
) : SpotifyGateway {
    private val mapper = ObjectMapper()
    private val client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build()

    override fun exchangeCode(code: String, redirectUri: String) = tokens(form(mapOf(
        "grant_type" to "authorization_code", "code" to code, "redirect_uri" to redirectUri,
    )))

    override fun refresh(refreshToken: String) = tokens(form(mapOf("grant_type" to "refresh_token", "refresh_token" to refreshToken)), refreshToken)

    override fun profile(accessToken: String): SpotifyProfile {
        val root = api("/v1/me", "GET", accessToken)
        return SpotifyProfile(root.path("id").asText().required(), root.path("display_name").asText().ifBlank { "Spotify" })
    }

    override fun devices(accessToken: String): List<SpotifyDevice> = api("/v1/me/player/devices", "GET", accessToken)
        .path("devices").mapNotNull { node ->
            node.path("id").asText().takeIf(String::isNotBlank)?.let { id -> SpotifyDevice(
                id, node.path("name").asText("Spotify Connect"), node.path("type").asText("unknown"),
                node.path("is_active").asBoolean(), node.path("is_restricted").asBoolean(),
                node.path("volume_percent").takeUnless { it.isNull || it.isMissingNode }?.asInt(),
                node.path("supports_volume").asBoolean(),
            ) }
        }

    override fun transfer(accessToken: String, deviceId: String, play: Boolean) {
        api("/v1/me/player", "PUT", accessToken, mapper.writeValueAsString(mapOf("device_ids" to listOf(deviceId), "play" to play)))
    }

    private fun form(values: Map<String, String>): HttpResponse<String> {
        if (clientId.isBlank() || clientSecret.isBlank()) throw SpotifyNotConfiguredException()
        val body = values.entries.joinToString("&") { "${encode(it.key)}=${encode(it.value)}" }
        val basic = Base64.getEncoder().encodeToString("$clientId:$clientSecret".toByteArray())
        val request = HttpRequest.newBuilder(URI("https://accounts.spotify.com/api/token")).timeout(Duration.ofSeconds(10))
            .header("Authorization", "Basic $basic").header("Content-Type", "application/x-www-form-urlencoded")
            .POST(HttpRequest.BodyPublishers.ofString(body)).build()
        return send(request)
    }

    private fun tokens(response: HttpResponse<String>, previousRefreshToken: String? = null): SpotifyTokens {
        if (response.statusCode() !in 200..299) throw SpotifyProviderException(response.statusCode())
        val root = mapper.readTree(response.body())
        return SpotifyTokens(root.path("access_token").asText().required(), root.path("refresh_token").asText(previousRefreshToken).required(),
            root.path("expires_in").asLong(3600), root.path("scope").asText("user-read-playback-state user-modify-playback-state"))
    }

    private fun api(path: String, method: String, token: String, body: String? = null): com.fasterxml.jackson.databind.JsonNode {
        val builder = HttpRequest.newBuilder(URI("https://api.spotify.com$path")).timeout(Duration.ofSeconds(10))
            .header("Authorization", "Bearer $token")
        if (body != null) builder.header("Content-Type", "application/json")
        val response = send(builder.method(method, body?.let(HttpRequest.BodyPublishers::ofString) ?: HttpRequest.BodyPublishers.noBody()).build())
        if (response.statusCode() == 204) return mapper.createObjectNode()
        if (response.statusCode() !in 200..299) throw SpotifyProviderException(response.statusCode())
        return mapper.readTree(response.body())
    }

    private fun send(request: HttpRequest) = try { client.send(request, HttpResponse.BodyHandlers.ofString()) }
        catch (_: Exception) { throw SpotifyUnavailableException() }
    private fun encode(value: String) = URLEncoder.encode(value, StandardCharsets.UTF_8)
    private fun String.required() = takeIf(String::isNotBlank) ?: throw SpotifyInvalidResponseException()
}

class SpotifyNotConfiguredException : RuntimeException()
class SpotifyUnavailableException : RuntimeException()
class SpotifyInvalidResponseException : RuntimeException()
class SpotifyProviderException(val providerStatus: Int) : RuntimeException()
