package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.ObjectMapper
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows

class SpotifyRecentPlaylistsTest {
    private val mapper = ObjectMapper()
    @Test
    fun `fills recent playlists from the library without duplicates and caps at six`() {
        fun playlist(id: Int) = SpotifyPlaylist(id.toString(), "Playlist $id", null, "https://open.spotify.com/playlist/$id")
        val library = (1..10).map(::playlist)
        assertEquals(listOf(3, 2, 1, 4, 5, 6).map(::playlist), spotifyPlaylistSelection(listOf(playlist(3), playlist(2)), library))
        assertEquals(library.take(6), spotifyPlaylistSelection(emptyList(), library))
        assertEquals(listOf(playlist(1)), spotifyPlaylistSelection(listOf(playlist(1)), emptyList()))
    }
    @Test
    fun `missing API metadata falls back to public title and cover without embedding HTML`() {
        val id = "1234567890123456789012"
        val value = spotifyPlaylistMetadata(id, { throw SpotifyProviderException(404) }, {
            mapper.readTree("""{"title":"Recent playlist","thumbnail_url":"https://i.scdn.co/image/test","html":"untrusted"}""")
        })!!
        assertEquals(id, value.path("id").asText())
        assertEquals("Recent playlist", value.path("name").asText())
        assertFalse(value.has("html"))
        assertEquals("https://i.scdn.co/image/test", value.path("images").path(0).path("url").asText())
        assertNull(spotifyPlaylistMetadata(id, { throw SpotifyProviderException(404) }, { throw SpotifyProviderException(404) }))
        assertThrows<SpotifyProviderException> {
            spotifyPlaylistMetadata(id, { throw SpotifyProviderException(429) }, { fail("Must not mask rate limiting") })
        }
        assertThrows<SpotifyInvalidResponseException> {
            spotifyPlaylistMetadata(id, { throw SpotifyProviderException(404) }, { mapper.readTree("{}") })
        }
    }
    private fun play(id: Int, second: Int, type: String = "playlist") = mapOf(
        "played_at" to "2026-09-05T12:00:${second.toString().padStart(2, '0')}Z",
        "context" to mapOf("type" to type, "uri" to "spotify:$type:${id.toString().padStart(22, '0')}"),
    )

    @Test
    fun `sorts by last play and deduplicates before limiting to six`() {
        val items = listOf(play(1, 1), play(2, 2), play(1, 9)) + (3..8).map { play(it, it) }
        val root = mapper.valueToTree<com.fasterxml.jackson.databind.JsonNode>(mapOf("items" to items))
        assertEquals(listOf(1, 8, 7, 6, 5, 4).map { it.toString().padStart(22, '0') }, recentSpotifyPlaylistIds(root))
    }

    @Test
    fun `missing non playlist or malformed contexts never become fallback playlists`() {
        val items = listOf(null, play(1, 1, "album"), mapOf("context" to null),
            mapOf("played_at" to "invalid", "context" to mapOf("type" to "playlist", "uri" to "spotify:playlist:1234567890123456789012")),
            mapOf("played_at" to "2026-09-05T12:00:00Z", "context" to mapOf("type" to "playlist", "uri" to "https://untrusted/playlist")))
        assertTrue(recentSpotifyPlaylistIds(mapper.valueToTree(mapOf("items" to items))).isEmpty())
        assertTrue(recentSpotifyPlaylistIds(mapper.readTree("{\"items\":[]}")).isEmpty())
        assertThrows<SpotifyInvalidResponseException> { recentSpotifyPlaylistIds(mapper.readTree("{}")) }
    }
}
