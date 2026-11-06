package dev.kyrion.core.calendar

import dev.kyrion.core.security.ForbiddenException
import dev.kyrion.core.security.RbacService
import dev.kyrion.core.security.authenticatedUserId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.*
import java.sql.Timestamp
import java.time.Duration
import java.time.Instant
import java.util.UUID

data class HouseholdCopyLink(val eventId: UUID, val remoteId: String, val etag: String, val revision: Long)

@Repository
class HouseholdCopyLinksRepository(private val jdbc: JdbcClient) {
    fun find(space: UUID, actor: UUID, connection: UUID, calendar: String, start: Instant?, end: Instant?): List<HouseholdCopyLink> {
        val range = if (start != null) " AND e.ends_at>:start AND e.starts_at<:end" else ""
        val query = jdbc.sql("""SELECT e.id,d.remote_id,d.etag,e.revision FROM household_calendar_delivery d
            JOIN household_calendar_event e ON e.id=d.event_id AND e.space_id=d.space_id
            JOIN household_calendar_destination g ON g.id=d.grant_id AND g.space_id=d.space_id AND g.user_id=d.target_user_id
            JOIN integration_connection c ON c.id=g.connection_id AND c.owner_id=g.user_id AND c.provider='google'
            WHERE d.space_id=:space AND d.target_user_id=:actor AND g.active
            AND c.id=:connection AND g.calendar_id=:calendar AND d.state='SYNCED'
            AND d.etag IS NOT NULL AND d.delivered_revision=e.revision
            AND EXISTS(SELECT 1 FROM household_calendar_participant p WHERE p.event_id=e.id AND p.space_id=e.space_id AND p.user_id=:actor)
            $range ORDER BY e.starts_at,e.id LIMIT 1001""")
            .param("space", space).param("actor", actor).param("connection", connection).param("calendar", calendar)
        if (start != null) query.param("start", Timestamp.from(start)).param("end", Timestamp.from(end!!))
        return query.query { rs, _ -> HouseholdCopyLink(rs.getObject("id", UUID::class.java), rs.getString("remote_id"), rs.getString("etag"), rs.getLong("revision")) }.list()
    }
}

@Service
class HouseholdCopyLinksService(private val repository: HouseholdCopyLinksRepository,
    private val connections: CalendarDisclosureRepository, private val rbac: RbacService) {
    fun links(actor: UUID, calendar: String, start: Instant? = null, end: Instant? = null): List<HouseholdCopyLink> {
        rbac.require(actor, "calendar:read")
        val space = rbac.workspace(actor)
        if (!connections.home(space)) throw ForbiddenException()
        if (calendar.isBlank() || calendar.length > 512 || (start == null) != (end == null) ||
            (start != null && (end!! <= start || Duration.between(start, end) > Duration.ofDays(400) ||
                start < Instant.parse("0001-01-01T00:00:00Z") || end > Instant.parse("9999-12-31T23:59:59Z")))) invalid()
        if (calendar == "primary") return emptyList() // Never infer a concrete calendar from an email address.
        try { rbac.require(actor, "calendar:create"); rbac.require(actor, "calendar:update") } catch (_: ForbiddenException) { return emptyList() }
        val connection = connections.connection(actor) ?: return emptyList()
        val links = repository.find(space, actor, connection, calendar, start, end)
        if (links.size > 1000) throw HouseholdCopyLinksFailure("HOUSEHOLD_COPY_LINKS_RANGE_TOO_LARGE")
        return links.filter { it.etag.isNotBlank() && it.etag.length <= 512 && it.etag.none { char -> char == '\r' || char == '\n' } }
    }
    private fun invalid(): Nothing = throw HouseholdCopyLinksFailure("HOUSEHOLD_COPY_LINKS_INVALID")
}

@RestController
@RequestMapping("/v1/calendar/household-copy-links")
class HouseholdCopyLinksController(private val service: HouseholdCopyLinksService) {
    @ModelAttribute fun noStore(response: jakarta.servlet.http.HttpServletResponse) { response.setHeader("Cache-Control", "no-store") }
    @GetMapping fun links(request: HttpServletRequest, @RequestParam calendarId: String,
        @RequestParam(required = false) start: String?, @RequestParam(required = false) end: String?) =
        service.links(request.authenticatedUserId(), calendarId, instant(start), instant(end))
    private fun instant(value: String?): Instant? = value?.let { runCatching { Instant.parse(it) }.getOrElse { throw HouseholdCopyLinksFailure("HOUSEHOLD_COPY_LINKS_INVALID") } }
}
class HouseholdCopyLinksFailure(val code: String) : RuntimeException(code)
@RestControllerAdvice(assignableTypes = [HouseholdCopyLinksController::class])
class HouseholdCopyLinksErrors {
    @ExceptionHandler(HouseholdCopyLinksFailure::class)
    fun failure(error: HouseholdCopyLinksFailure) = ResponseEntity.status(HttpStatus.BAD_REQUEST).body(mapOf("code" to error.code))
    @ExceptionHandler(org.springframework.web.bind.MissingServletRequestParameterException::class,
        org.springframework.web.method.annotation.MethodArgumentTypeMismatchException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST) fun invalid() = mapOf("code" to "HOUSEHOLD_COPY_LINKS_INVALID")
}
