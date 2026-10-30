package dev.kyrion.core.conversation

import dev.kyrion.core.activity.*
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestControllerAdvice
import java.util.UUID

/** Core authorizes disclosure; provider adapters never decide memory permissions. */
@Service
class CloudContextPolicy(
    private val activity: ActivityService,
    @Value("\${kyrion.ai.cloud-enabled:false}") private val enabled: Boolean = false,
) {
    fun authorize(actor: UUID, provider: String?, consent: String?, correlation: UUID) {
        if (provider == null && consent == null) return
        if (!enabled || provider !in setOf("openai", "anthropic", "gemini") || consent != "current_message") {
            throw CloudProcessingDenied()
        }
        activity.record(
            ActivityCategory.INTEGRATION, "ai.cloud.context.authorized", ActivityStatus.CONFIRMED,
            ActivityActorType.USER, "kyrion-core", "ai.cloud.current_message.$provider",
            actor.toString(), correlation, actor,
        )
    }
}

@ResponseStatus(HttpStatus.FORBIDDEN)
class CloudProcessingDenied : RuntimeException()

@RestControllerAdvice
class CloudContextErrorHandler {
    @ExceptionHandler(CloudProcessingDenied::class)
    @ResponseStatus(HttpStatus.FORBIDDEN)
    fun denied() = mapOf("code" to "CLOUD_NOT_ALLOWED")
}
