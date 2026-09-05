package dev.kyrion.core.integration

import dev.kyrion.core.activity.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import java.util.UUID

class YouTubeLinksTest {
    private val id = "M7lc1UVf-VE"

    @Test
    fun `supported video links resolve without forwarding tracking data`() {
        listOf("https://www.youtube.com/watch?v=$id&si=private", "https://youtu.be/$id?si=private",
            "https://m.youtube.com/shorts/$id", "https://youtube.com/live/$id",
            "https://music.youtube.com/watch?v=$id&list=RD$id").forEach { link ->
            val result = YouTubeLinks.resolve(link, YouTubeSource.VIDEO)
            assertEquals("https://www.youtube-nocookie.com/embed/$id?playsinline=1&autoplay=0", result.embedUrl)
            assertEquals("https://www.youtube.com/watch?v=$id", result.watchUrl)
        }
    }

    @Test
    fun `music links retain a direct music destination and playlists remain playlists`() {
        assertEquals("https://music.youtube.com/watch?v=$id", YouTubeLinks.resolve("https://youtu.be/$id", YouTubeSource.MUSIC).watchUrl)
        val playlist = "PL1234567890_abc"
        val result = YouTubeLinks.resolve("https://www.youtube.com/playlist?list=$playlist", YouTubeSource.VIDEO)
        assertEquals("https://www.youtube-nocookie.com/embed/videoseries?list=$playlist&playsinline=1&autoplay=0", result.embedUrl)
    }

    @Test
    fun `rejects arbitrary hosts credentials ports ambiguous parameters and invalid identifiers`() {
        listOf("http://youtube.com/watch?v=$id", "https://youtube.com.evil.test/watch?v=$id",
            "https://youtube.com@evil.test/watch?v=$id", "https://user@youtube.com/watch?v=$id",
            "https://youtube.com:8443/watch?v=$id", "https://127.0.0.1/watch?v=$id",
            "javascript:alert(1)", "https://youtube.com/watch?v=$id&v=$id",
            "https://youtube.com/watch?v=short", "https://youtu.be/$id/extra",
            "https://youtube.com/playlist?list=a%26autoplay%3D1", "https://youtube.com/redirect?q=$id",
            "https://youtube.com/watch?v=%ZZ", "x".repeat(2049)).forEach { link ->
            assertThrows<InvalidYouTubeLinkException>(link) { YouTubeLinks.resolve(link, YouTubeSource.VIDEO) }
        }
    }

    @Test
    fun `audit records preparation and owner without retaining links`() {
        val events = mutableListOf<ActivityEvent>()
        val service = YouTubeIntegrationService(ActivityService(object : ActivityEventRepository {
            override fun append(event: ActivityEvent) = event.also(events::add)
            override fun findRecent(limit: Int) = emptyList<ActivityEvent>()
        }))
        val owner = UUID.randomUUID()
        service.prepare(owner, PrepareYouTubeRequest("https://youtu.be/$id", YouTubeSource.VIDEO))
        assertEquals(owner, events.single().ownerId)
        assertEquals("YOUTUBE_EMBED_PREPARED", events.single().summaryCode)
        assertFalse(events.single().toString().contains(id))
        assertThrows<InvalidYouTubeLinkException> { service.prepare(owner, PrepareYouTubeRequest("https://evil.test", YouTubeSource.VIDEO)) }
        assertEquals(1, events.size)
    }
}
