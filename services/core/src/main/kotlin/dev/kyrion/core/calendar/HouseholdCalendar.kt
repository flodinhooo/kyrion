package dev.kyrion.core.calendar

import com.fasterxml.jackson.databind.DeserializationFeature
import com.fasterxml.jackson.databind.MapperFeature
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.*
import dev.kyrion.core.security.ForbiddenException
import dev.kyrion.core.security.RbacService
import dev.kyrion.core.security.authenticatedUserId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import org.springframework.web.bind.annotation.*
import java.sql.Timestamp
import java.time.Instant
import java.time.ZoneId
import java.util.UUID

data class HouseholdCalendarMember(val id: UUID, val username: String)
data class HouseholdEventCreate(
    val title: String, val startsAt: Instant, val endsAt: Instant, val timeZone: String,
    val description: String? = null, val participantIds: List<UUID> = emptyList(),
)
data class HouseholdEventUpdate(
    val title: String, val startsAt: Instant, val endsAt: Instant, val timeZone: String,
    val revision: Long, val description: String? = null,
)
data class HouseholdCalendarEvent(
    val id: UUID, val createdBy: UUID, val title: String, val description: String?,
    val startsAt: Instant, val endsAt: Instant, val timeZone: String, val revision: Long,
    val participantIds: List<UUID>, val canEdit: Boolean = false, val canDelete: Boolean = false,
)

@Repository
class HouseholdCalendarRepository(private val jdbc: JdbcClient) {
    fun members(space: UUID): List<HouseholdCalendarMember> = jdbc.sql(
        "SELECT id,username FROM user_account WHERE space_id=:space AND enabled ORDER BY username,id"
    ).param("space", space).query { rs, _ -> HouseholdCalendarMember(rs.getObject("id", UUID::class.java), rs.getString("username")) }.list()

    fun isHome(space: UUID): Boolean = jdbc.sql("SELECT EXISTS(SELECT 1 FROM kyrion_space WHERE id=:space AND type='HOME' AND status='ACTIVE')")
        .param("space", space).query(Boolean::class.java).single()

    fun all(space: UUID, start: Instant?, end: Instant?): List<HouseholdCalendarEvent> {
        val range = if (start != null) " AND ends_at>:start AND starts_at<:end" else ""
        val query = jdbc.sql("SELECT * FROM household_calendar_event WHERE space_id=:space$range ORDER BY starts_at,id LIMIT 1001").param("space", space)
        if (start != null) query.param("start", Timestamp.from(start)).param("end", Timestamp.from(end!!))
        return query.query { rs, _ -> map(rs) }.list()
    }

    fun find(space: UUID, id: UUID, lock: Boolean = false): HouseholdCalendarEvent? = jdbc.sql(
        "SELECT * FROM household_calendar_event WHERE space_id=:space AND id=:id" + if (lock) " FOR UPDATE" else ""
    ).param("space", space).param("id", id).query { rs, _ -> map(rs) }.optional().orElse(null)

    fun create(space: UUID, actor: UUID, body: HouseholdEventCreate, participants: List<UUID>): HouseholdCalendarEvent {
        val id = UUID.randomUUID()
        jdbc.sql("""INSERT INTO household_calendar_event(id,space_id,created_by,title,description,starts_at,ends_at,time_zone)
            VALUES(:id,:space,:actor,:title,:description,:start,:end,:zone)""")
            .param("id", id).param("space", space).param("actor", actor).param("title", body.title.trim())
            .param("description", body.description).param("start", Timestamp.from(body.startsAt))
            .param("end", Timestamp.from(body.endsAt)).param("zone", body.timeZone).update()
        participants.forEach { participant ->
            jdbc.sql("INSERT INTO household_calendar_participant(event_id,space_id,user_id) VALUES(:id,:space,:user)")
                .param("id", id).param("space", space).param("user", participant).update()
        }
        return find(space, id)!!
    }

    fun update(space: UUID, id: UUID, body: HouseholdEventUpdate): HouseholdCalendarEvent {
        val changed = jdbc.sql("""UPDATE household_calendar_event SET title=:title,description=:description,
            starts_at=:start,ends_at=:end,time_zone=:zone,revision=revision+1,updated_at=CURRENT_TIMESTAMP
            WHERE space_id=:space AND id=:id AND revision=:revision""")
            .param("title", body.title.trim()).param("description", body.description)
            .param("start", Timestamp.from(body.startsAt)).param("end", Timestamp.from(body.endsAt)).param("zone", body.timeZone)
            .param("space", space).param("id", id).param("revision", body.revision).update()
        if (changed != 1) throw HouseholdCalendarFailure("HOUSEHOLD_CALENDAR_CONFLICT", HttpStatus.CONFLICT)
        return find(space, id)!!
    }

    fun delete(space: UUID, id: UUID, revision: Long) {
        if (jdbc.sql("DELETE FROM household_calendar_event WHERE space_id=:space AND id=:id AND revision=:revision")
                .param("space", space).param("id", id).param("revision", revision).update() != 1)
            throw HouseholdCalendarFailure("HOUSEHOLD_CALENDAR_CONFLICT", HttpStatus.CONFLICT)
    }

    private fun map(rs: java.sql.ResultSet): HouseholdCalendarEvent {
        val id = rs.getObject("id", UUID::class.java)
        val participants = jdbc.sql("SELECT user_id FROM household_calendar_participant WHERE event_id=:id AND space_id=:space ORDER BY user_id")
            .param("id", id).param("space", rs.getObject("space_id", UUID::class.java)).query(UUID::class.java).list().filterNotNull()
        return HouseholdCalendarEvent(id, rs.getObject("created_by", UUID::class.java), rs.getString("title"), rs.getString("description"),
            rs.getTimestamp("starts_at").toInstant(), rs.getTimestamp("ends_at").toInstant(), rs.getString("time_zone"), rs.getLong("revision"), participants)
    }
}

@Service
class HouseholdCalendarService(
    private val repository: HouseholdCalendarRepository, private val rbac: RbacService, private val activity: ActivityService,
) {
    fun members(actor: UUID): List<HouseholdCalendarMember> {
        val space = readSpace(actor)
        return eligibleMembers(space)
    }

    fun all(actor: UUID, start: Instant? = null, end: Instant? = null): List<HouseholdCalendarEvent> {
        val space = readSpace(actor)
        if ((start == null) != (end == null) || (start != null &&
                (!validInstant(start) || !validInstant(end!!) || end <= start ||
                    java.time.Duration.between(start, end) > java.time.Duration.ofDays(400)))) invalid()
        val events = repository.all(space, start, end)
        if (events.size > 1000) throw HouseholdCalendarFailure("HOUSEHOLD_CALENDAR_RANGE_TOO_LARGE", HttpStatus.BAD_REQUEST)
        return events.map { view(actor, it) }
    }

    @Transactional
    fun create(actor: UUID, body: HouseholdEventCreate): HouseholdCalendarEvent {
        val space = mutationSpace(actor, "calendar:create")
        rbac.require(actor, "calendar:read")
        validate(body.title, body.description, body.startsAt, body.endsAt, body.timeZone)
        if (body.participantIds.size > 50 || body.participantIds.distinct().size != body.participantIds.size) invalid()
        val participants = (body.participantIds + actor).distinct().sorted()
        if (participants.size > 50 || !eligibleMembers(space).map { it.id }.containsAll(participants)) invalid()
        val event = repository.create(space, actor, body, participants)
        audit(space, actor, event.id, "created")
        return view(actor, event)
    }

    @Transactional
    fun update(actor: UUID, id: UUID, body: HouseholdEventUpdate): HouseholdCalendarEvent {
        val space = mutationSpace(actor, "calendar:update")
        rbac.require(actor, "calendar:read")
        val event = repository.find(space, id, true) ?: notFound()
        if (actor !in event.participantIds) throw ForbiddenException()
        if (body.revision < 0) invalid()
        if (body.revision != event.revision) throw HouseholdCalendarFailure("HOUSEHOLD_CALENDAR_CONFLICT", HttpStatus.CONFLICT)
        validate(body.title, body.description, body.startsAt, body.endsAt, body.timeZone)
        val result = repository.update(space, id, body)
        audit(space, actor, id, "updated")
        return view(actor, result)
    }

    @Transactional
    fun delete(actor: UUID, id: UUID, revision: Long) {
        val space = mutationSpace(actor, "calendar:delete")
        rbac.require(actor, "calendar:read")
        val event = repository.find(space, id, true) ?: notFound()
        if (actor != event.createdBy) throw ForbiddenException()
        if (revision < 0) invalid()
        repository.delete(space, id, revision)
        audit(space, actor, id, "deleted")
    }

    private fun eligibleMembers(space: UUID) = repository.members(space).filter { member ->
        try { rbac.require(member.id, "calendar:read"); true } catch (_: ForbiddenException) { false }
    }
    private fun readSpace(actor: UUID): UUID { rbac.require(actor, "calendar:read"); return requireHome(rbac.workspace(actor)) }
    private fun mutationSpace(actor: UUID, permission: String) = requireHome(rbac.authorizeMutation(actor, permission))
    private fun requireHome(space: UUID): UUID { if (!repository.isHome(space)) throw ForbiddenException(); return space }
    private fun view(actor: UUID, event: HouseholdCalendarEvent): HouseholdCalendarEvent {
        val permissions = rbac.permissions(actor)
        return event.copy(canEdit = actor in event.participantIds && "calendar:update" in permissions,
            canDelete = actor == event.createdBy && "calendar:delete" in permissions)
    }
    private fun validate(title: String, description: String?, start: Instant, end: Instant, zone: String) {
        if (title.isBlank() || title.length > 500 || (description?.length ?: 0) > 10000 ||
            !validInstant(start) || !validInstant(end) || !end.isAfter(start) || zone.length > 120) invalid()
        try { ZoneId.of(zone) } catch (_: java.time.DateTimeException) { invalid() }
    }
    private fun audit(space: UUID, actor: UUID, event: UUID, operation: String) = activity.record(
        ActivityCategory.SECURITY, "calendar.household.$operation", ActivityStatus.SUCCEEDED, ActivityActorType.USER,
        "kyrion-core", event.toString(), actor.toString(), UUID.randomUUID(), space,
    )
    private fun invalid(): Nothing = throw HouseholdCalendarFailure("HOUSEHOLD_CALENDAR_INVALID", HttpStatus.BAD_REQUEST)
    private fun notFound(): Nothing = throw HouseholdCalendarFailure("HOUSEHOLD_CALENDAR_NOT_FOUND", HttpStatus.NOT_FOUND)
    private fun validInstant(value: Instant) = value >= Instant.parse("0001-01-01T00:00:00Z") && value <= Instant.parse("9999-12-31T23:59:59Z")
}

@RestController
@RequestMapping("/v1/calendar/household-events")
class HouseholdCalendarController(private val service: HouseholdCalendarService) {
    @ModelAttribute
    fun noStore(response: jakarta.servlet.http.HttpServletResponse) { response.setHeader("Cache-Control", "no-store") }

    private val json = jacksonObjectMapper().findAndRegisterModules()
        // The existing Jackson 2 request mapper has no jsr310 module; Spring's
        // Jackson 3 response support does not supply one. Keep input strict and
        // parse only ISO instants without introducing another dependency.
        .registerModule(com.fasterxml.jackson.databind.module.SimpleModule().addDeserializer(Instant::class.java,
            object : com.fasterxml.jackson.databind.JsonDeserializer<Instant>() {
                override fun deserialize(parser: com.fasterxml.jackson.core.JsonParser,
                    context: com.fasterxml.jackson.databind.DeserializationContext): Instant {
                    if (!parser.hasToken(com.fasterxml.jackson.core.JsonToken.VALUE_STRING)) invalid()
                    return instant(parser.text) ?: invalid()
                }
            }))
        .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true)
        .configure(DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES, true)
        .configure(DeserializationFeature.FAIL_ON_TRAILING_TOKENS, true)
        .configure(DeserializationFeature.ACCEPT_FLOAT_AS_INT, false)
        .configure(MapperFeature.ALLOW_COERCION_OF_SCALARS, false)

    @GetMapping
    fun all(request: HttpServletRequest, @RequestParam(required = false) start: String?, @RequestParam(required = false) end: String?): List<HouseholdCalendarEvent> =
        service.all(request.authenticatedUserId(), instant(start), instant(end))
    @GetMapping("/members") fun members(request: HttpServletRequest) = service.members(request.authenticatedUserId())
    @PostMapping @ResponseStatus(HttpStatus.CREATED)
    fun create(request: HttpServletRequest, @RequestBody raw: String) = service.create(request.authenticatedUserId(), parse(raw, HouseholdEventCreate::class.java))
    @PutMapping("/{id}")
    fun update(request: HttpServletRequest, @PathVariable id: UUID, @RequestBody raw: String) = service.update(request.authenticatedUserId(), id, parse(raw, HouseholdEventUpdate::class.java))
    @DeleteMapping("/{id}") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun delete(request: HttpServletRequest, @PathVariable id: UUID, @RequestParam revision: String) {
        val value = revision.takeIf { it.matches(Regex("0|[1-9][0-9]*")) }?.toLongOrNull() ?: invalid()
        service.delete(request.authenticatedUserId(), id, value)
    }
    private fun instant(value: String?): Instant? = value?.let { try { Instant.parse(it) } catch (_: Exception) { invalid() } }
    private fun <T> parse(raw: String, type: Class<T>): T {
        if (raw.length > 32000) invalid()
        return try {
            val root = json.readTree(raw)
            if (!root.isObject) invalid()
            if (listOf("title", "startsAt", "endsAt", "timeZone").any { !root.path(it).isTextual }) invalid()
            if (root.has("description") && !root.get("description").isNull && !root.get("description").isTextual) invalid()
            if (type == HouseholdEventUpdate::class.java && (!root.path("revision").isIntegralNumber ||
                    !root.path("revision").canConvertToLong() || root.path("revision").asLong() < 0)) invalid()
            if (root.has("participantIds")) {
                val participants = root.get("participantIds")
                if (!participants.isArray || participants.size() > 50 || participants.any { !it.isTextual }) invalid()
            }
            json.readValue(raw, type)
        } catch (_: Exception) { invalid() }
    }
    private fun invalid(): Nothing = throw HouseholdCalendarFailure("HOUSEHOLD_CALENDAR_INVALID", HttpStatus.BAD_REQUEST)
}

class HouseholdCalendarFailure(val code: String, val status: HttpStatus) : RuntimeException(code)

@RestControllerAdvice(assignableTypes = [HouseholdCalendarController::class])
class HouseholdCalendarErrors {
    @ExceptionHandler(HouseholdCalendarFailure::class)
    fun failure(error: HouseholdCalendarFailure) = ResponseEntity.status(error.status).body(mapOf("code" to error.code))
    @ExceptionHandler(org.springframework.web.bind.MissingServletRequestParameterException::class,
        org.springframework.web.method.annotation.MethodArgumentTypeMismatchException::class,
        org.springframework.http.converter.HttpMessageNotReadableException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = mapOf("code" to "HOUSEHOLD_CALENDAR_INVALID")
}
