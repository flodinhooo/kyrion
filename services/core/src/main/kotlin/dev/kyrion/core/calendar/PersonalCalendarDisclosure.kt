package dev.kyrion.core.calendar

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.*
import dev.kyrion.core.integration.GoogleCalendarEvents
import dev.kyrion.core.integration.GoogleIntegrationService
import dev.kyrion.core.security.ForbiddenException
import dev.kyrion.core.security.RbacService
import dev.kyrion.core.security.authenticatedUserId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.support.TransactionTemplate
import org.springframework.web.bind.annotation.*
import java.security.MessageDigest
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.util.UUID

enum class CalendarVisibility { PRIVATE, AVAILABILITY, DETAILS }
data class CalendarDisclosureSetting(val id: UUID, val calendarId: String, val visibility: CalendarVisibility, val revision: Long)
data class CalendarDisclosureChange(val calendarId: String, val visibility: CalendarVisibility, val revision: Long)
data class SharedCalendarSource(val id: UUID, val userId: UUID, val username: String, val visibility: CalendarVisibility)
data class DisclosedCalendarEvent(val id: String, val startsAt: String, val endsAt: String, val title: String?, val description: String?)
data class DisclosedCalendarEvents(val source: SharedCalendarSource, val items: List<DisclosedCalendarEvent>)
internal data class DisclosureRow(val id: UUID, val space: UUID, val user: UUID, val connection: UUID,
    val calendar: String, val visibility: CalendarVisibility, val revision: Long, val username: String) {
    fun setting() = CalendarDisclosureSetting(id, calendar, visibility, revision)
    fun source() = SharedCalendarSource(id, user, username, visibility)
}

@Repository
class CalendarDisclosureRepository(private val jdbc: JdbcClient) {
    internal fun rows(space: UUID): List<DisclosureRow> = jdbc.sql("""SELECT d.*,u.username
        FROM personal_calendar_disclosure d JOIN user_account u ON u.id=d.user_id AND u.space_id=d.space_id
        JOIN integration_connection c ON c.id=d.connection_id AND c.owner_id=d.user_id AND c.provider='google'
        WHERE d.space_id=:space AND u.enabled ORDER BY u.username,d.id""").param("space", space).query { rs, _ ->
        DisclosureRow(rs.getObject("id", UUID::class.java), rs.getObject("space_id", UUID::class.java),
            rs.getObject("user_id", UUID::class.java), rs.getObject("connection_id", UUID::class.java),
            rs.getString("calendar_id"), CalendarVisibility.valueOf(rs.getString("visibility")), rs.getLong("revision"), rs.getString("username"))
    }.list()
    fun connection(user: UUID): UUID? = jdbc.sql("SELECT id FROM integration_connection WHERE owner_id=:user AND provider='google'")
        .param("user", user).query(UUID::class.java).optional().orElse(null)
    fun home(space: UUID) = jdbc.sql("SELECT EXISTS(SELECT 1 FROM kyrion_space WHERE id=:space AND type='HOME' AND status='ACTIVE')")
        .param("space", space).query(Boolean::class.java).single()
    internal fun save(space: UUID, actor: UUID, connection: UUID, body: CalendarDisclosureChange, old: DisclosureRow?): UUID {
        val id = old?.id ?: UUID.randomUUID()
        jdbc.sql("""INSERT INTO personal_calendar_disclosure(id,space_id,user_id,connection_id,calendar_id,visibility,revision)
            VALUES(:id,:space,:user,:connection,:calendar,:visibility,1)
            ON CONFLICT(connection_id,calendar_id) DO UPDATE SET visibility=EXCLUDED.visibility,
            revision=personal_calendar_disclosure.revision+1,updated_at=CURRENT_TIMESTAMP""")
            .param("id", id).param("space", space).param("user", actor).param("connection", connection)
            .param("calendar", body.calendarId).param("visibility", body.visibility.name).update()
        return id
    }
}

@Service
class PersonalCalendarDisclosureService(
    private val repository: CalendarDisclosureRepository, private val rbac: RbacService,
    private val google: GoogleIntegrationService, private val activity: ActivityService,
    private val transactions: TransactionTemplate,
) {
    fun settings(actor: UUID): List<CalendarDisclosureSetting> = transaction {
        repository.rows(readSpace(actor)).filter { it.user == actor }.map { it.setting() }
    }

    fun change(actor: UUID, body: CalendarDisclosureChange): CalendarDisclosureSetting {
        if (body.calendarId.isBlank() || body.calendarId.length > 512 || body.calendarId == "primary" || body.revision < 0) invalid()
        val connection = transaction {
            val space = readSpace(actor)
            rbac.require(actor, "calendar:update")
            val current = repository.rows(space).find { it.user == actor && it.calendar == body.calendarId }
            // Revocation must work even when the provider is offline or disconnected.
            if (body.visibility == CalendarVisibility.PRIVATE && current != null) return@transaction current.connection
            repository.connection(actor) ?: missing()
        }
        // A positive disclosure must select an actual readable calendar, never an alias.
        if (body.visibility != CalendarVisibility.PRIVATE && google.calendars(actor).items.none {
                it.id == body.calendarId && it.accessRole in setOf("owner", "writer", "reader") }) invalid()
        return transaction {
            val space = rbac.authorizeMutation(actor, "calendar:update")
            requireHome(space); rbac.require(actor, "calendar:read")
            if (repository.connection(actor) != connection) missing()
            val rows = repository.rows(space).filter { it.user == actor }
            val old = rows.find { it.connection == connection && it.calendar == body.calendarId }
            if ((old?.revision ?: 0) != body.revision) conflict()
            if (old == null && rows.size >= 50) invalid()
            val id = repository.save(space, actor, connection, body, old)
            activity.record(ActivityCategory.SECURITY, "calendar.disclosure.changed", ActivityStatus.SUCCEEDED, ActivityActorType.USER,
                "kyrion-core", id.toString(), actor.toString(), UUID.randomUUID(), space)
            repository.rows(space).first { it.id == id }.setting()
        }
    }

    fun sources(actor: UUID): List<SharedCalendarSource> = transaction {
        val space = readSpace(actor)
        repository.rows(space).filter { it.user != actor && it.visibility != CalendarVisibility.PRIVATE && eligible(it, space) }.map { it.source() }
    }

    fun events(actor: UUID, id: UUID, start: Instant, end: Instant): DisclosedCalendarEvents {
        if (!end.isAfter(start) || Duration.between(start, end) > Duration.ofDays(400) ||
            start < Instant.parse("0001-01-01T00:00:00Z") || end > Instant.parse("9999-12-31T23:59:59Z")) invalid()
        val before = transaction { authorized(actor, id) }
        val remote = google.events(before.user, before.calendar, start.toString(), end.toString(), before.connection)
        return transaction {
            // Serialize the final redaction decision with role/disclosure mutations.
            rbac.authorizeMutation(actor, "calendar:read")
            val current = authorized(actor, id)
            if (current != before) conflict()
            DisclosedCalendarEvents(current.source(), redact(current, remote))
        }
    }

    private fun authorized(actor: UUID, id: UUID): DisclosureRow {
        val space = readSpace(actor)
        val row = repository.rows(space).find { it.id == id && it.user != actor && it.visibility != CalendarVisibility.PRIVATE } ?: missing()
        if (!eligible(row, space)) missing()
        return row
    }
    private fun eligible(row: DisclosureRow, space: UUID): Boolean = try {
        rbac.require(row.user, "calendar:read")
        rbac.workspace(row.user) == space && repository.connection(row.user) == row.connection
    } catch (_: ForbiddenException) { false }
    private fun readSpace(actor: UUID): UUID { rbac.require(actor, "calendar:read"); return requireHome(rbac.workspace(actor)) }
    private fun requireHome(space: UUID): UUID { if (!repository.home(space)) throw ForbiddenException(); return space }
    private fun redact(row: DisclosureRow, response: GoogleCalendarEvents): List<DisclosedCalendarEvent> {
        if (response.items.size > 10000) invalid()
        return response.items.filter { it.status != "cancelled" }.mapNotNull { event ->
            if (event.id.isBlank() || event.id.length > 2048) return@mapNotNull null
            val start = event.start ?: return@mapNotNull null
            val end = event.end ?: return@mapNotNull null
            val valid = runCatching {
                if (start.matches(Regex("\\d{4}-\\d{2}-\\d{2}"))) LocalDate.parse(end).isAfter(LocalDate.parse(start))
                else Instant.parse(end).isAfter(Instant.parse(start))
            }.getOrDefault(false)
            if (!valid) return@mapNotNull null
            val opaque = MessageDigest.getInstance("SHA-256").digest("${row.id}:${event.id}".toByteArray(Charsets.UTF_8))
                .joinToString("") { "%02x".format(it) }
            val details = row.visibility == CalendarVisibility.DETAILS
            DisclosedCalendarEvent(opaque, start, end, if (details) event.summary.take(500) else null,
                if (details) event.description?.take(10000) else null)
        }
    }
    private fun <T : Any> transaction(action: () -> T): T = transactions.execute { action() }
    private fun invalid(): Nothing = throw CalendarDisclosureFailure("CALENDAR_DISCLOSURE_INVALID", HttpStatus.BAD_REQUEST)
    private fun missing(): Nothing = throw CalendarDisclosureFailure("CALENDAR_DISCLOSURE_NOT_FOUND", HttpStatus.NOT_FOUND)
    private fun conflict(): Nothing = throw CalendarDisclosureFailure("CALENDAR_DISCLOSURE_CONFLICT", HttpStatus.CONFLICT)
}

@RestController
@RequestMapping("/v1/calendar/personal-disclosure")
class PersonalCalendarDisclosureController(private val service: PersonalCalendarDisclosureService) {
    @ModelAttribute fun noStore(response: jakarta.servlet.http.HttpServletResponse) { response.setHeader("Cache-Control", "no-store") }
    @GetMapping fun settings(request: HttpServletRequest) = service.settings(request.authenticatedUserId())
    @GetMapping("/sources") fun sources(request: HttpServletRequest) = service.sources(request.authenticatedUserId())
    @PutMapping fun change(request: HttpServletRequest, @RequestBody raw: String): CalendarDisclosureSetting {
        val body = try {
            if (raw.length > 4000) invalid()
            val root = jacksonObjectMapper().readTree(raw)
            if (!root.isObject || root.fieldNames().asSequence().toSet() != setOf("calendarId", "visibility", "revision") ||
                !root.path("calendarId").isTextual || !root.path("visibility").isTextual ||
                !root.path("revision").isIntegralNumber || !root.path("revision").canConvertToLong()) invalid()
            CalendarDisclosureChange(root.path("calendarId").asText(), CalendarVisibility.valueOf(root.path("visibility").asText()), root.path("revision").asLong())
        } catch (_: Exception) { invalid() }
        return service.change(request.authenticatedUserId(), body)
    }
    @GetMapping("/sources/{id}/events")
    fun events(request: HttpServletRequest, @PathVariable id: UUID, @RequestParam start: String, @RequestParam end: String): DisclosedCalendarEvents {
        val from = runCatching { Instant.parse(start) }.getOrElse { invalid() }
        val until = runCatching { Instant.parse(end) }.getOrElse { invalid() }
        return service.events(request.authenticatedUserId(), id, from, until)
    }
    private fun invalid(): Nothing = throw CalendarDisclosureFailure("CALENDAR_DISCLOSURE_INVALID", HttpStatus.BAD_REQUEST)
}
class CalendarDisclosureFailure(val code: String, val status: HttpStatus) : RuntimeException(code)
@RestControllerAdvice(assignableTypes = [PersonalCalendarDisclosureController::class])
class CalendarDisclosureErrors {
    @ExceptionHandler(CalendarDisclosureFailure::class)
    fun failure(error: CalendarDisclosureFailure) = ResponseEntity.status(error.status).body(mapOf("code" to error.code))
    @ExceptionHandler(org.springframework.web.bind.MissingServletRequestParameterException::class,
        org.springframework.web.method.annotation.MethodArgumentTypeMismatchException::class,
        org.springframework.http.converter.HttpMessageNotReadableException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST) fun invalid() = mapOf("code" to "CALENDAR_DISCLOSURE_INVALID")
}
