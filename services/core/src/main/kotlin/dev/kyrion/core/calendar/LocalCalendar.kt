package dev.kyrion.core.calendar

import dev.kyrion.core.security.authenticatedUserId
import dev.kyrion.core.security.RbacService
import dev.kyrion.core.activity.*
import org.springframework.transaction.annotation.Transactional
import jakarta.servlet.http.HttpServletRequest
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.web.bind.annotation.*
import org.springframework.http.HttpStatus
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.sql.Timestamp
import java.time.Instant
import java.util.UUID
import tools.jackson.databind.annotation.JsonDeserialize
import tools.jackson.databind.ValueDeserializer
import tools.jackson.databind.DeserializationContext
import tools.jackson.core.JsonParser
import tools.jackson.core.JsonToken

data class LocalCalendarEvent(val id: UUID, val title: String, val description: String?, val startsAt: Instant, val endsAt: Instant, val timeZone: String, val syncToGoogle: Boolean, val googleCalendarId: String? = null, val googleEventId: String? = null)
data class LocalCalendarEventRequest(val title: String, val description: String? = null, val startsAt: Instant, val endsAt: Instant, val timeZone: String? = null,
    @field:JsonDeserialize(using = CalendarBooleanDeserializer::class) val syncToGoogle: Boolean? = null)

class CalendarBooleanDeserializer : ValueDeserializer<Boolean>() {
    override fun deserialize(parser: JsonParser, context: DeserializationContext): Boolean = when (parser.currentToken()) {
        JsonToken.VALUE_TRUE -> true
        JsonToken.VALUE_FALSE -> false
        else -> throw InvalidCalendarEvent()
    }
}

@org.springframework.stereotype.Repository
class LocalCalendarRepository(private val jdbc: JdbcClient) {
    fun findAll(owner: UUID): List<LocalCalendarEvent> = jdbc.sql("SELECT * FROM local_calendar_event WHERE owner_id=:owner ORDER BY starts_at, title").param("owner", owner).query { rs, _ -> map(rs) }.list()
    fun find(owner: UUID, id: UUID): LocalCalendarEvent? = jdbc.sql("SELECT * FROM local_calendar_event WHERE owner_id=:owner AND id=:id").param("owner", owner).param("id", id).query { rs, _ -> map(rs) }.optional().orElse(null)
    fun save(owner: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent { validate(body); val id=UUID.randomUUID(); val now=Timestamp.from(Instant.now()); jdbc.sql("INSERT INTO local_calendar_event(id,owner_id,title,description,starts_at,ends_at,time_zone,content_fingerprint,sync_to_google,created_at,updated_at) VALUES(:id,:owner,:title,:description,:startsAt,:endsAt,:timeZone,:fingerprint,:sync,:created,:updated)").param("id",id).param("owner",owner).param("title",body.title.trim()).param("description",body.description).param("startsAt",Timestamp.from(body.startsAt)).param("endsAt",Timestamp.from(body.endsAt)).param("timeZone",body.timeZone ?: "UTC").param("fingerprint",fingerprint(owner,body)).param("sync",body.syncToGoogle ?: false).param("created",now).param("updated",now).update(); return find(owner,id)!! }
    fun update(owner: UUID, id: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent? { validate(body); val count=jdbc.sql("UPDATE local_calendar_event SET title=:title,description=:description,starts_at=:startsAt,ends_at=:endsAt,time_zone=:timeZone,content_fingerprint=:fingerprint,sync_to_google=:sync,updated_at=:updated WHERE owner_id=:owner AND id=:id").param("owner",owner).param("id",id).param("title",body.title.trim()).param("description",body.description).param("startsAt",Timestamp.from(body.startsAt)).param("endsAt",Timestamp.from(body.endsAt)).param("timeZone",body.timeZone ?: "UTC").param("fingerprint",fingerprint(owner,body)).param("sync",body.syncToGoogle ?: false).param("updated",Timestamp.from(Instant.now())).update(); return if(count==1) find(owner,id) else null }
    fun delete(owner: UUID,id: UUID)=jdbc.sql("DELETE FROM local_calendar_event WHERE owner_id=:owner AND id=:id").param("owner",owner).param("id",id).update()==1
    private fun validate(body: LocalCalendarEventRequest) { if(body.title.isBlank() || body.title.length > 500 || (body.description?.length ?: 0) > 10000 || !body.endsAt.isAfter(body.startsAt)) throw InvalidCalendarEvent(); try { java.time.ZoneId.of(body.timeZone ?: "UTC") } catch (_: java.time.DateTimeException) { throw InvalidCalendarEvent() } }
    private fun fingerprint(owner: UUID,b: LocalCalendarEventRequest)=MessageDigest.getInstance("SHA-256").digest("$owner|${b.title.trim()}|${b.startsAt}|${b.endsAt}|${b.timeZone ?: "UTC"}".toByteArray(StandardCharsets.UTF_8)).joinToString(""){ "%02x".format(it) }
    private fun map(rs: java.sql.ResultSet)=LocalCalendarEvent(rs.getObject("id",UUID::class.java),rs.getString("title"),rs.getString("description"),rs.getTimestamp("starts_at").toInstant(),rs.getTimestamp("ends_at").toInstant(),rs.getString("time_zone"),rs.getBoolean("sync_to_google"),rs.getString("google_calendar_id"),rs.getString("google_event_id"))
}

@org.springframework.stereotype.Service
class LocalCalendarService(private val repository: LocalCalendarRepository, private val rbac: RbacService, private val activity: ActivityService) {
    fun all(actor: UUID): List<LocalCalendarEvent> {
        rbac.require(actor, "calendar:read")
        return repository.findAll(rbac.workspace(actor))
    }
    @Transactional
    fun create(actor: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent {
        rbac.authorizeMutation(actor, "calendar:create")
        return repository.save(rbac.workspace(actor), body).also { audit(actor, "calendar.event.created", it.id) }
    }
    @Transactional
    fun update(actor: UUID, id: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent {
        rbac.authorizeMutation(actor, "calendar:update")
        val event = repository.update(rbac.workspace(actor), id, body) ?: throw CalendarEventNotFound()
        audit(actor, "calendar.event.updated", id)
        return event
    }
    @Transactional
    fun delete(actor: UUID, id: UUID) {
        rbac.authorizeMutation(actor, "calendar:delete")
        if (!repository.delete(rbac.workspace(actor), id)) throw CalendarEventNotFound()
        audit(actor, "calendar.event.deleted", id)
    }
    private fun audit(actor: UUID, type: String, id: UUID) = activity.record(
        ActivityCategory.SECURITY, type, ActivityStatus.SUCCEEDED, ActivityActorType.USER,
        "kyrion-core", id.toString(), actor.toString(), ownerId = rbac.workspace(actor),
    )
}

@RestController
@RequestMapping("/v1/calendar/events")
class LocalCalendarController(private val service: LocalCalendarService) {
    @GetMapping fun all(request: HttpServletRequest) = service.all(request.authenticatedUserId())
    @PostMapping fun create(@RequestBody body: LocalCalendarEventRequest, request: HttpServletRequest) = service.create(request.authenticatedUserId(), body)
    @PutMapping("/{id}") fun update(@PathVariable id: UUID, @RequestBody body: LocalCalendarEventRequest, request: HttpServletRequest) = service.update(request.authenticatedUserId(), id, body)
    @DeleteMapping("/{id}") fun delete(@PathVariable id: UUID, request: HttpServletRequest) = service.delete(request.authenticatedUserId(), id)
}
@ResponseStatus(HttpStatus.NOT_FOUND)
class CalendarEventNotFound: RuntimeException()
@ResponseStatus(HttpStatus.BAD_REQUEST)
class InvalidCalendarEvent: RuntimeException()

@RestControllerAdvice
class CalendarErrorHandler {
    @ExceptionHandler(InvalidCalendarEvent::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = mapOf("code" to "CALENDAR_EVENT_INVALID")
}
