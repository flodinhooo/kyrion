package dev.kyrion.core.conversation

import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Pattern
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.*
import java.time.Clock
import java.time.Instant
import java.util.UUID

data class ConversationMessageRequest(
    val id: UUID,
    @field:Pattern(regexp = "user|assistant") val role: String,
    @field:NotBlank @field:Size(max = 100_000) val content: String,
    val createdAt: Instant,
)
data class SaveConversationRequest(
    @field:NotBlank @field:Size(max = 160) val title: String,
    @field:Size(min = 1, max = 200) @field:Valid val messages: List<ConversationMessageRequest>,
)
data class ConversationListResponse(val items: List<ConversationSummary>)
data class RenameConversationRequest(@field:NotBlank @field:Size(max = 160) val title: String)

@RestController
@RequestMapping("/v1/conversations")
class ConversationController(
    private val repository: ConversationRepository,
    private val clock: Clock = Clock.systemUTC(),
) {
    @GetMapping fun recent(request: HttpServletRequest) = ConversationListResponse(repository.recent(request.ownerId(), 30))

    @GetMapping("/{id}") fun find(@PathVariable id: UUID, request: HttpServletRequest): Conversation =
        repository.find(request.ownerId(), id) ?: throw ConversationNotFoundException()

    @PutMapping("/{id}") fun replace(@PathVariable id: UUID, @Valid @RequestBody body: SaveConversationRequest, request: HttpServletRequest): Conversation {
        val existing = repository.find(request.ownerId(), id)
        val now = clock.instant()
        return repository.replace(request.ownerId(), Conversation(
            id, body.title.trim(), existing?.createdAt ?: now, now,
            body.messages.map { ConversationMessage(it.id, it.role, it.content, it.createdAt) },
        ))
    }

    @PatchMapping("/{id}") fun rename(
        @PathVariable id: UUID,
        @Valid @RequestBody body: RenameConversationRequest,
        request: HttpServletRequest,
    ): ConversationSummary = repository.rename(request.ownerId(), id, body.title.trim(), clock.instant())
        ?: throw ConversationNotFoundException()

    @DeleteMapping("/{id}") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun delete(@PathVariable id: UUID, request: HttpServletRequest) {
        if (!repository.delete(request.ownerId(), id)) throw ConversationNotFoundException()
    }

    private fun HttpServletRequest.ownerId(): UUID =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw ConversationUnauthenticatedException()
}

class ConversationUnauthenticatedException : RuntimeException()

@RestControllerAdvice
class ConversationErrorHandler {
    @ExceptionHandler(ConversationNotFoundException::class) @ResponseStatus(HttpStatus.NOT_FOUND)
    fun notFound() = mapOf("code" to "CONVERSATION_NOT_FOUND")
    @ExceptionHandler(ConversationUnauthenticatedException::class) @ResponseStatus(HttpStatus.UNAUTHORIZED)
    fun unauthenticated() = mapOf("code" to "UNAUTHENTICATED")
}
