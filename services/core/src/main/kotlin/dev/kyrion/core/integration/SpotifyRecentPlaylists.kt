package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.JsonNode
import java.time.Instant

internal fun spotifyPlaylistMetadata(id: String, details: () -> JsonNode, preview: () -> JsonNode): JsonNode? {
    require(Regex("[A-Za-z0-9]{22}").matches(id))
    try { return details() }
    catch (error: SpotifyProviderException) {
        if (error.providerStatus !in setOf(403, 404)) throw error
    }
    val embed = try { preview() }
    catch (error: SpotifyProviderException) {
        if (error.providerStatus in setOf(403, 404)) return null
        throw error
    }
    if (!embed.path("title").isTextual || embed.path("title").asText().isBlank()) throw SpotifyInvalidResponseException()
    // Reuse the normal playlist validation, including the cover-host allowlist.
    return com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.objectNode().apply {
        put("id", id)
        put("name", embed.path("title").asText())
        putArray("images").addObject().put("url", embed.path("thumbnail_url").asText(""))
    }
}

/** Use only reported playlist contexts, never infer a playlist from a track. */
internal fun recentSpotifyPlaylistIds(root: JsonNode): List<String> {
    val items = root.path("items")
    if (!items.isArray) throw SpotifyInvalidResponseException()
    return items.take(50).mapNotNull { item ->
        val context = item.path("context")
        if (context.path("type").asText() != "playlist") return@mapNotNull null
        val id = Regex("spotify:playlist:([A-Za-z0-9]{22})").matchEntire(context.path("uri").asText())
            ?.groupValues?.get(1) ?: return@mapNotNull null
        val playedAt = runCatching { Instant.parse(item.path("played_at").asText()) }.getOrNull()
            ?: return@mapNotNull null
        id to playedAt
    }.sortedByDescending { it.second }.map { it.first }.distinct().take(6)
}
