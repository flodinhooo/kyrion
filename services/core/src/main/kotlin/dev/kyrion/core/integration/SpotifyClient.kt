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
data class SpotifyPlayback(val playing: Boolean, val title: String?, val artist: String?, val imageUrl: String?, val trackUrl: String?, val progressMs: Int, val durationMs: Int, val deviceId: String?, val disallowed: List<String>)
enum class SpotifyPlaybackAction { RESUME, PAUSE, NEXT, PREVIOUS, VOLUME, SEEK }
data class SpotifyPlaybackCommand(val action: SpotifyPlaybackAction, val deviceId: String, val volumePercent: Int? = null, val positionMs: Int? = null)
data class SpotifyPlaylist(val id: String, val name: String, val imageUrl: String?, val url: String)

internal fun spotifyApiResponse(mapper: ObjectMapper, status: Int, body: String, read: Boolean): com.fasterxml.jackson.databind.JsonNode {
    if (status !in 200..299) throw SpotifyProviderException(status)
    // Player commands may succeed with an empty 200 as well as the documented 204.
    if (status == 204 || !read) return mapper.createObjectNode()
    if (body.isBlank()) throw SpotifyInvalidResponseException()
    return try { mapper.readTree(body) ?: throw SpotifyInvalidResponseException() }
        catch (_: com.fasterxml.jackson.core.JsonProcessingException) { throw SpotifyInvalidResponseException() }
}

interface SpotifyGateway {
    fun exchangeCode(code: String, redirectUri: String): SpotifyTokens
    fun refresh(refreshToken: String): SpotifyTokens
    fun profile(accessToken: String): SpotifyProfile
    fun devices(accessToken: String): List<SpotifyDevice>
    fun transfer(accessToken: String, deviceId: String, play: Boolean)
    fun playback(accessToken: String): SpotifyPlayback
    fun control(accessToken: String, command: SpotifyPlaybackCommand)
    fun playlists(accessToken: String): List<SpotifyPlaylist>
    fun playPlaylist(accessToken: String, playlistId: String, deviceId: String)
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

    override fun playlists(accessToken: String): List<SpotifyPlaylist> = recentSpotifyPlaylistIds(
        api("/v1/me/player/recently-played?limit=50", "GET", accessToken),
    ).mapNotNull { playlistId ->
            val item = spotifyPlaylistMetadata(playlistId,
                { api("/v1/playlists/$playlistId?fields=id,name,images", "GET", accessToken) },
                {
                    // Public Spotify preview, without account credentials or embedded HTML.
                    val request = HttpRequest.newBuilder(URI("https://open.spotify.com/oembed?url=${encode("https://open.spotify.com/playlist/$playlistId")}"))
                        .timeout(Duration.ofSeconds(5)).GET().build()
                    val response = send(request)
                    spotifyApiResponse(mapper, response.statusCode(), response.body(), true)
                },
            ) ?: return@mapNotNull null
            val id = item.path("id").asText()
            val name = item.path("name").asText()
            if (!Regex("[A-Za-z0-9]{22}").matches(id) || name.isBlank()) return@mapNotNull null
            val image = item.path("images").path(0).path("url").asText().takeIf { url ->
                runCatching { URI(url).let { it.scheme == "https" && it.host in setOf("i.scdn.co", "mosaic.scdn.co", "image-cdn-ak.spotifycdn.com", "image-cdn-fa.spotifycdn.com") && it.userInfo == null } }.getOrDefault(false)
            }
            SpotifyPlaylist(id, name, image, "https://open.spotify.com/playlist/$id")
        }

    override fun playPlaylist(accessToken: String, playlistId: String, deviceId: String) {
        api("/v1/me/player/play?device_id=${encode(deviceId)}", "PUT", accessToken,
            mapper.writeValueAsString(mapOf("context_uri" to "spotify:playlist:$playlistId")))
    }

    override fun playback(accessToken: String): SpotifyPlayback {
        val root = api("/v1/me/player", "GET", accessToken)
        val item = root.path("item")
        val actions = root.path("actions")
        // Spotify has returned restrictions both directly and nested under disallows.
        val restrictions = actions.path("disallows").takeIf { it.isObject } ?: actions
        fun safeUrl(value: String, host: String) = value.takeIf {
            runCatching { URI(it).let { uri -> uri.scheme == "https" && uri.host == host && uri.userInfo == null } }.getOrDefault(false)
        }
        return SpotifyPlayback(
            root.path("is_playing").asBoolean(), item.path("name").asText().takeIf(String::isNotBlank),
            item.path("artists").map { it.path("name").asText() }.filter(String::isNotBlank).joinToString(", ").ifBlank { item.path("show").path("name").asText() }.takeIf(String::isNotBlank),
            safeUrl((item.path("album").path("images").takeIf { it.isArray } ?: item.path("images")).path(0).path("url").asText(), "i.scdn.co"),
            safeUrl(item.path("external_urls").path("spotify").asText(), "open.spotify.com"),
            root.path("progress_ms").asInt().coerceAtLeast(0), item.path("duration_ms").asInt().coerceAtLeast(0),
            root.path("device").path("id").asText().takeIf(String::isNotBlank),
            restrictions.properties().filter { it.value.asBoolean() }.map { it.key },
        )
    }

    override fun control(accessToken: String, command: SpotifyPlaybackCommand) {
        val endpoint = when (command.action) {
            SpotifyPlaybackAction.RESUME -> "play"
            SpotifyPlaybackAction.PAUSE -> "pause"
            SpotifyPlaybackAction.NEXT -> "next"
            SpotifyPlaybackAction.PREVIOUS -> "previous"
            SpotifyPlaybackAction.VOLUME -> "volume"
            SpotifyPlaybackAction.SEEK -> "seek"
        }
        val volume = when (command.action) {
            SpotifyPlaybackAction.VOLUME -> "&volume_percent=${command.volumePercent}"
            SpotifyPlaybackAction.SEEK -> "&position_ms=${command.positionMs}"
            else -> ""
        }
        val method = if (command.action in setOf(SpotifyPlaybackAction.NEXT, SpotifyPlaybackAction.PREVIOUS)) "POST" else "PUT"
        api("/v1/me/player/$endpoint?device_id=${encode(command.deviceId)}$volume", method, accessToken)
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
            root.path("expires_in").asLong(3600), root.path("scope").asText(""))
    }

    private fun api(path: String, method: String, token: String, body: String? = null): com.fasterxml.jackson.databind.JsonNode {
        val builder = HttpRequest.newBuilder(URI("https://api.spotify.com$path")).timeout(Duration.ofSeconds(10))
            .header("Authorization", "Bearer $token")
        if (body != null) builder.header("Content-Type", "application/json")
        val response = send(builder.method(method, body?.let(HttpRequest.BodyPublishers::ofString) ?: HttpRequest.BodyPublishers.noBody()).build())
        return spotifyApiResponse(mapper, response.statusCode(), response.body(), method == "GET")
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
