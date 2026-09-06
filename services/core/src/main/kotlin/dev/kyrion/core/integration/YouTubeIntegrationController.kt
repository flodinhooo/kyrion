package dev.kyrion.core.integration

import dev.kyrion.core.activity.*
import dev.kyrion.core.security.workspaceOwnerId
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.*
import java.net.URI
import java.net.URLDecoder
import java.nio.charset.StandardCharsets
import java.util.UUID

enum class YouTubeSource { VIDEO, MUSIC }
data class PrepareYouTubeRequest(@field:NotBlank @field:Size(max = 2048) val url: String, val source: YouTubeSource)
data class YouTubeEmbed(val embedUrl: String, val watchUrl: String)

/** Resolves links locally; never fetches an owner-supplied URL or extracts a media stream. */
object YouTubeLinks {
    fun resolve(input: String, source: YouTubeSource): YouTubeEmbed {
        if (input.length > 2048) throw InvalidYouTubeLinkException()
        val uri = try { URI(input.trim()) } catch (_: Exception) { throw InvalidYouTubeLinkException() }
        val host = uri.host?.lowercase()
        if (uri.scheme != "https" || uri.userInfo != null || uri.port != -1 || host !in setOf("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be")) throw InvalidYouTubeLinkException()
        val query = try {
            uri.rawQuery.orEmpty().split('&').filter(String::isNotBlank).map {
                val parts = it.split('=', limit = 2)
                URLDecoder.decode(parts[0], StandardCharsets.UTF_8) to URLDecoder.decode(parts.getOrElse(1) { "" }, StandardCharsets.UTF_8)
            }
        } catch (_: Exception) { throw InvalidYouTubeLinkException() }
        if (query.count { it.first == "v" } > 1 || query.count { it.first == "list" } > 1) throw InvalidYouTubeLinkException()
        val path = uri.path.orEmpty().trimEnd('/')
        val videoId = when {
            host == "youtu.be" -> path.removePrefix("/")
            path == "/watch" -> query.firstOrNull { it.first == "v" }?.second
            path.startsWith("/shorts/") -> path.removePrefix("/shorts/")
            path.startsWith("/live/") -> path.removePrefix("/live/")
            else -> null
        }
        val watchHost = if (source == YouTubeSource.MUSIC) "music.youtube.com" else "www.youtube.com"
        if (videoId != null && Regex("[A-Za-z0-9_-]{11}").matches(videoId)) {
            return YouTubeEmbed("https://www.youtube-nocookie.com/embed/$videoId?playsinline=1&autoplay=0", "https://$watchHost/watch?v=$videoId")
        }
        val playlist = query.firstOrNull { it.first == "list" }?.second
        if (host != "youtu.be" && path == "/playlist" && playlist != null && Regex("[A-Za-z0-9_-]{10,128}").matches(playlist)) {
            return YouTubeEmbed("https://www.youtube-nocookie.com/embed/videoseries?list=$playlist&playsinline=1&autoplay=0", "https://$watchHost/playlist?list=$playlist")
        }
        throw InvalidYouTubeLinkException()
    }
}

@Service
class YouTubeIntegrationService(private val activity: ActivityService) {
    fun prepare(ownerId: UUID, request: PrepareYouTubeRequest): YouTubeEmbed {
        val embed = YouTubeLinks.resolve(request.url, request.source)
        // Preparation is audited, but does not claim the browser actually played the video.
        activity.record(ActivityCategory.INTEGRATION, "youtube.embed.prepared", ActivityStatus.SUCCEEDED,
            ActivityActorType.USER, "youtube", "YOUTUBE_EMBED_PREPARED", ownerId.toString(), ownerId = ownerId)
        return embed
    }
}

@RestController
@RequestMapping("/v1/integrations/youtube")
class YouTubeIntegrationController(private val service: YouTubeIntegrationService) {
    @PostMapping("/embed")
    fun prepare(@Valid @RequestBody body: PrepareYouTubeRequest, request: HttpServletRequest): YouTubeEmbed {
        val ownerId = request.workspaceOwnerId()
        return service.prepare(ownerId, body)
    }
}

class InvalidYouTubeLinkException : RuntimeException()

@RestControllerAdvice
class YouTubeErrorHandler {
    @ExceptionHandler(InvalidYouTubeLinkException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalidLink() = mapOf("code" to "YOUTUBE_INVALID_LINK")
}
