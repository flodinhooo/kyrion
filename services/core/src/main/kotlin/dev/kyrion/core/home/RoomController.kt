package dev.kyrion.core.home

import dev.kyrion.core.activity.*
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.*
import java.time.Clock
import java.util.UUID
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.integration.IntegrationConnectionView
import dev.kyrion.core.integration.view

data class RoomNameRequest(@field:NotBlank @field:Size(max = 120) val name: String)
data class RoomAssignmentRequest(val roomId: UUID?)

@RestController
@RequestMapping("/v1/home")
class RoomController(
    private val rooms: RoomRepository,
    private val activity: ActivityService,
    private val connections: IntegrationConnectionRepository,
    private val clock: Clock = Clock.systemUTC(),
) {
    @GetMapping("/rooms") fun rooms(request: HttpServletRequest) = rooms.all(request.ownerId())
    @PostMapping("/rooms") @ResponseStatus(HttpStatus.CREATED)
    fun create(@Valid @RequestBody body: RoomNameRequest, request: HttpServletRequest): Room {
        val ownerId = request.ownerId(); val now = clock.instant()
        return rooms.create(ownerId, Room(UUID.randomUUID(), body.name.trim(), now, now)).also { record(ownerId, "home.room.created", "room.created", it.id) }
    }
    @PatchMapping("/rooms/{id}") fun rename(@PathVariable id: UUID, @Valid @RequestBody body: RoomNameRequest, request: HttpServletRequest): Room {
        val ownerId = request.ownerId(); return (rooms.rename(ownerId, id, body.name.trim(), clock.instant()) ?: throw RoomNotFoundException()).also { record(ownerId, "home.room.renamed", "room.renamed", id) }
    }
    @DeleteMapping("/rooms/{id}") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun delete(@PathVariable id: UUID, request: HttpServletRequest) { val ownerId = request.ownerId(); if (!rooms.delete(ownerId, id)) throw RoomNotFoundException(); record(ownerId, "home.room.deleted", "room.deleted", id) }
    @PutMapping("/connections/{id}/room") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun assign(@PathVariable id: UUID, @RequestBody body: RoomAssignmentRequest, request: HttpServletRequest) { val ownerId = request.ownerId(); if (!rooms.assignConnection(ownerId, id, body.roomId)) throw RoomAssignmentException(); record(ownerId, "home.device.assigned", "device.room.assigned", id) }
    @PatchMapping("/connections/{id}")
    fun renameDevice(@PathVariable id: UUID, @Valid @RequestBody body: RoomNameRequest, request: HttpServletRequest): IntegrationConnectionView {
        val ownerId = request.ownerId()
        val updated = connections.rename(ownerId, id, body.name.trim(), clock.instant()) ?: throw RoomAssignmentException()
        record(ownerId, "home.device.renamed", "device.renamed", id)
        return updated.view()
    }
    private fun record(ownerId: UUID, type: String, summary: String, correlationId: UUID) = activity.record(ActivityCategory.INTEGRATION, type, ActivityStatus.SUCCEEDED, ActivityActorType.USER, "kyrion-core", summary, ownerId.toString(), correlationId)
    private fun HttpServletRequest.ownerId() = getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw RoomUnauthenticatedException()
}
class RoomNotFoundException : RuntimeException()
class RoomConflictException : RuntimeException()
class RoomAssignmentException : RuntimeException()
class RoomUnauthenticatedException : RuntimeException()
@RestControllerAdvice class RoomErrorHandler {
    @ExceptionHandler(RoomNotFoundException::class) @ResponseStatus(HttpStatus.NOT_FOUND) fun missing() = mapOf("code" to "ROOM_NOT_FOUND")
    @ExceptionHandler(RoomConflictException::class) @ResponseStatus(HttpStatus.CONFLICT) fun conflict() = mapOf("code" to "ROOM_NAME_CONFLICT")
    @ExceptionHandler(RoomAssignmentException::class) @ResponseStatus(HttpStatus.BAD_REQUEST) fun assignment() = mapOf("code" to "ROOM_ASSIGNMENT_INVALID")
    @ExceptionHandler(RoomUnauthenticatedException::class) @ResponseStatus(HttpStatus.UNAUTHORIZED) fun unauthenticated() = mapOf("code" to "UNAUTHENTICATED")
}
