package dev.kyrion.core.memory

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.conversation.ConversationRepository
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Pattern
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.*
import java.time.Clock
import java.util.UUID

data class MemorySettingsRequest(val enabled: Boolean)
data class MemoryProposalRequest(
    @field:Pattern(regexp = "preference|person|project|value|other") val category: String,
    @field:NotBlank @field:Size(max = 1_000) val content: String,
    @field:Pattern(regexp = "standard|sensitive") val sensitivity: String,
    val sourceConversationId: UUID? = null,
    val sourceMessageId: UUID? = null,
)
data class MemoryUpdateRequest(
    @field:Pattern(regexp = "preference|person|project|value|other") val category: String,
    @field:NotBlank @field:Size(max = 1_000) val content: String,
    @field:Pattern(regexp = "standard|sensitive") val sensitivity: String,
)

@RestController
@RequestMapping("/v1/memory")
class PersonalMemoryController(
    private val repository: PersonalMemoryRepository,
    private val conversations: ConversationRepository,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) {
    @GetMapping fun profile(request: HttpServletRequest): MemoryProfile {
        val ownerId = request.ownerId()
        return MemoryProfile(repository.settings(ownerId), repository.recent(ownerId, 100))
    }

    @PutMapping("/settings")
    fun settings(@Valid @RequestBody body: MemorySettingsRequest, request: HttpServletRequest): MemorySettings {
        val ownerId = request.ownerId()
        val result = repository.updateSettings(ownerId, body.enabled, clock.instant())
        record(ownerId, "memory.settings.updated", if (body.enabled) "memory.enabled" else "memory.disabled")
        return result
    }

    @PostMapping("/proposals") @ResponseStatus(HttpStatus.CREATED)
    fun propose(@Valid @RequestBody body: MemoryProposalRequest, request: HttpServletRequest): PersonalMemory {
        val ownerId = request.ownerId()
        if (!repository.settings(ownerId).enabled) throw MemoryDisabledException()
        validateSource(ownerId, body.sourceConversationId, body.sourceMessageId)
        val now = clock.instant()
        val memory = repository.create(
            ownerId,
            PersonalMemory(
                UUID.randomUUID(), MemoryCategory.valueOf(body.category), body.content.trim(),
                MemorySensitivity.valueOf(body.sensitivity), "explicit", MemoryStatus.proposed,
                body.sourceConversationId, body.sourceMessageId, now, now, null,
            ),
        )
        record(ownerId, "memory.proposed", "memory.proposed", ActivityStatus.PROPOSED, memory.id)
        return memory
    }

    @PostMapping("/{id}/confirm")
    fun confirm(@PathVariable id: UUID, request: HttpServletRequest): PersonalMemory {
        val ownerId = request.ownerId()
        val memory = repository.find(ownerId, id) ?: throw MemoryNotFoundException()
        if (memory.status != MemoryStatus.proposed) throw MemoryConflictException()
        val confirmed = repository.confirm(ownerId, id, clock.instant()) ?: throw MemoryNotFoundException()
        record(ownerId, "memory.confirmed", "memory.confirmed", ActivityStatus.CONFIRMED, id)
        return confirmed
    }

    @PatchMapping("/{id}")
    fun update(
        @PathVariable id: UUID,
        @Valid @RequestBody body: MemoryUpdateRequest,
        request: HttpServletRequest,
    ): PersonalMemory {
        val ownerId = request.ownerId()
        val updated = repository.update(
            ownerId, id, MemoryCategory.valueOf(body.category), body.content.trim(),
            MemorySensitivity.valueOf(body.sensitivity), clock.instant(),
        ) ?: throw MemoryNotFoundException()
        record(ownerId, "memory.updated", "memory.updated", memoryId = id)
        return updated
    }

    @DeleteMapping("/{id}") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun delete(@PathVariable id: UUID, request: HttpServletRequest) {
        val ownerId = request.ownerId()
        if (!repository.delete(ownerId, id)) throw MemoryNotFoundException()
        record(ownerId, "memory.deleted", "memory.deleted", memoryId = id)
    }

    private fun validateSource(ownerId: UUID, conversationId: UUID?, messageId: UUID?) {
        if ((conversationId == null) != (messageId == null)) throw MemoryInvalidRequestException()
        if (conversationId == null || messageId == null) return
        val conversation = conversations.find(ownerId, conversationId) ?: throw MemoryInvalidRequestException()
        if (conversation.messages.none { it.id == messageId && it.role == "user" }) throw MemoryInvalidRequestException()
    }

    private fun record(
        ownerId: UUID,
        type: String,
        summary: String,
        status: ActivityStatus = ActivityStatus.SUCCEEDED,
        memoryId: UUID = UUID.randomUUID(),
    ) {
        activity.record(
            ActivityCategory.SECURITY, type, status, ActivityActorType.USER, "kyrion-core", summary,
            actorId = ownerId.toString(), correlationId = memoryId,
        )
    }

    private fun HttpServletRequest.ownerId(): UUID =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw MemoryUnauthenticatedException()
}

class MemoryNotFoundException : RuntimeException()
class MemoryDisabledException : RuntimeException()
class MemoryConflictException : RuntimeException()
class MemoryInvalidRequestException : RuntimeException()
class MemoryUnauthenticatedException : RuntimeException()

@RestControllerAdvice
class MemoryErrorHandler {
    @ExceptionHandler(MemoryNotFoundException::class) @ResponseStatus(HttpStatus.NOT_FOUND)
    fun notFound() = mapOf("code" to "MEMORY_NOT_FOUND")
    @ExceptionHandler(MemoryDisabledException::class) @ResponseStatus(HttpStatus.CONFLICT)
    fun disabled() = mapOf("code" to "MEMORY_DISABLED")
    @ExceptionHandler(MemoryConflictException::class) @ResponseStatus(HttpStatus.CONFLICT)
    fun conflict() = mapOf("code" to "MEMORY_CONFLICT")
    @ExceptionHandler(MemoryInvalidRequestException::class) @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = mapOf("code" to "INVALID_REQUEST")
    @ExceptionHandler(MemoryUnauthenticatedException::class) @ResponseStatus(HttpStatus.UNAUTHORIZED)
    fun unauthenticated() = mapOf("code" to "UNAUTHENTICATED")
}
