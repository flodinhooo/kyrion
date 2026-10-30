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

data class LocalCalendarEvent(val id: UUID, val title: String, val description: String?, val startsAt: Instant, val endsAt: Instant, val timeZone: String, val syncToGoogle: Boolean, val googleCalendarId: String? = null, val googleEventId: String? = null, val syncStatus: String = "local", val syncError: String? = null, val syncActorId: UUID? = null, val googleEtag: String? = null, val revision: Long = 0, val pendingDeletion: Boolean = false)
data class LocalCalendarEventRequest(val title: String, val description: String? = null, val startsAt: Instant, val endsAt: Instant, val timeZone: String? = null,
    @field:JsonDeserialize(using = CalendarBooleanDeserializer::class) val syncToGoogle: Boolean? = null, val googleCalendarId: String? = null, val revision: Long? = null)

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
    fun lockedFind(owner: UUID, id: UUID): LocalCalendarEvent? = jdbc.sql("SELECT * FROM local_calendar_event WHERE owner_id=:owner AND id=:id FOR UPDATE")
        .param("owner",owner).param("id",id).query { rs, _ -> map(rs) }.optional().orElse(null)
    fun save(owner: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent { validate(body); val id=UUID.randomUUID(); val now=Timestamp.from(Instant.now()); jdbc.sql("INSERT INTO local_calendar_event(id,owner_id,title,description,starts_at,ends_at,time_zone,content_fingerprint,sync_to_google,created_at,updated_at) VALUES(:id,:owner,:title,:description,:startsAt,:endsAt,:timeZone,:fingerprint,:sync,:created,:updated)").param("id",id).param("owner",owner).param("title",body.title.trim()).param("description",body.description).param("startsAt",Timestamp.from(body.startsAt)).param("endsAt",Timestamp.from(body.endsAt)).param("timeZone",body.timeZone ?: "UTC").param("fingerprint",fingerprint(owner,body)).param("sync",body.syncToGoogle ?: false).param("created",now).param("updated",now).update(); return find(owner,id)!! }
    fun update(owner: UUID, id: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent? { validate(body); val count=jdbc.sql("UPDATE local_calendar_event SET title=:title,description=:description,starts_at=:startsAt,ends_at=:endsAt,time_zone=:timeZone,content_fingerprint=:fingerprint,sync_to_google=:sync,updated_at=:updated WHERE owner_id=:owner AND id=:id").param("owner",owner).param("id",id).param("title",body.title.trim()).param("description",body.description).param("startsAt",Timestamp.from(body.startsAt)).param("endsAt",Timestamp.from(body.endsAt)).param("timeZone",body.timeZone ?: "UTC").param("fingerprint",fingerprint(owner,body)).param("sync",body.syncToGoogle ?: false).param("updated",Timestamp.from(Instant.now())).update(); return if(count==1) find(owner,id) else null }
    fun delete(owner: UUID,id: UUID)=jdbc.sql("DELETE FROM local_calendar_event WHERE owner_id=:owner AND id=:id").param("owner",owner).param("id",id).update()==1
    fun configureSync(owner: UUID, id: UUID, actor: UUID, body: LocalCalendarEventRequest, previous: LocalCalendarEvent?) {
        val enabled = body.syncToGoogle ?: false
        val calendar = body.googleCalendarId?.trim()?.takeIf { it.isNotEmpty() && it.length <= 512 }
        val configured = enabled && calendar != null
        if (previous?.googleEtag != null && enabled && calendar != previous.googleCalendarId) throw CalendarSyncConflict()
        jdbc.sql("""UPDATE local_calendar_event SET sync_actor_id=:actor,google_calendar_id=:calendar,
            google_event_id=:remote,google_etag=:etag,sync_status=:status,sync_error=NULL,revision=revision+1,
            pending_deletion=CASE WHEN :enabled THEN pending_deletion ELSE FALSE END WHERE owner_id=:owner AND id=:id""")
            .param("enabled", enabled).param("owner", owner).param("id", id).param("actor", if(configured) actor else null)
            .param("calendar", if(enabled) calendar else null)
            .param("remote", if(configured) previous?.googleEventId ?: id.toString().replace("-", "") else null)
            .param("etag", if(enabled) previous?.googleEtag else null)
            .param("status", if(configured) "pending" else if(enabled) "configuration_required" else "local").update()
    }
    fun completeDeletion(owner: UUID, event: LocalCalendarEvent) = jdbc.sql("DELETE FROM local_calendar_event WHERE owner_id=:owner AND id=:id AND revision=:revision AND pending_deletion=TRUE")
        .param("owner",owner).param("id",event.id).param("revision",event.revision).update()
    fun markDeletion(owner: UUID, id: UUID) {
        jdbc.sql("UPDATE local_calendar_event SET pending_deletion=TRUE,sync_status='pending',sync_error=NULL,revision=revision+1 WHERE owner_id=:owner AND id=:id")
            .param("owner",owner).param("id",id).update()
    }
    fun syncOutcome(owner: UUID, event: LocalCalendarEvent, status: String, error: String?, etag: String? = event.googleEtag) {
        jdbc.sql("""UPDATE local_calendar_event SET google_etag=:etag,sync_status=CASE WHEN revision=:revision THEN :status ELSE 'pending' END,
            sync_error=:error WHERE owner_id=:owner AND id=:id AND sync_actor_id=:actor AND google_event_id=:remote AND google_etag IS NOT DISTINCT FROM :previousEtag""")
            .param("owner",owner).param("id",event.id).param("revision",event.revision).param("status",status).param("error",error)
            .param("previousEtag",event.googleEtag).param("etag",etag).param("actor",event.syncActorId).param("remote",event.googleEventId).update()
    }
    fun acceptRemote(owner: UUID, event: LocalCalendarEvent, remote: dev.kyrion.core.integration.GoogleCalendarEvent) {
        val start = runCatching { java.time.OffsetDateTime.parse(remote.start).toInstant() }.getOrNull() ?: throw CalendarSyncConflict()
        val end = runCatching { java.time.OffsetDateTime.parse(remote.end).toInstant() }.getOrNull() ?: throw CalendarSyncConflict()
        if (!end.isAfter(start) || remote.recurring || remote.summary.length > 500 || (remote.description?.length ?: 0) > 10000) throw CalendarSyncConflict()
        jdbc.sql("""UPDATE local_calendar_event SET title=:title,description=:description,starts_at=:start,ends_at=:end,
            google_etag=:etag,sync_status='synced',sync_error=NULL,revision=revision+1,updated_at=CURRENT_TIMESTAMP,content_fingerprint=:fingerprint
            WHERE owner_id=:owner AND id=:id AND revision=:revision AND google_etag IS NOT DISTINCT FROM :previousEtag AND sync_status IN ('synced','read_error')""")
            .param("owner",owner).param("id",event.id).param("revision",event.revision).param("title",remote.summary)
            .param("fingerprint",fingerprint(owner, LocalCalendarEventRequest(remote.summary,remote.description,start,end,event.timeZone))).param("previousEtag",event.googleEtag).param("description",remote.description).param("start",Timestamp.from(start)).param("end",Timestamp.from(end)).param("etag",remote.etag).update()
    }
    private fun validate(body: LocalCalendarEventRequest) { if(body.title.isBlank() || body.title.length > 500 || (body.description?.length ?: 0) > 10000 || !body.endsAt.isAfter(body.startsAt)) throw InvalidCalendarEvent(); try { java.time.ZoneId.of(body.timeZone ?: "UTC") } catch (_: java.time.DateTimeException) { throw InvalidCalendarEvent() } }
    private fun fingerprint(owner: UUID,b: LocalCalendarEventRequest)=MessageDigest.getInstance("SHA-256").digest("$owner|${b.title.trim()}|${b.startsAt}|${b.endsAt}|${b.timeZone ?: "UTC"}".toByteArray(StandardCharsets.UTF_8)).joinToString(""){ "%02x".format(it) }
    internal fun map(rs: java.sql.ResultSet)=LocalCalendarEvent(rs.getObject("id",UUID::class.java),rs.getString("title"),rs.getString("description"),rs.getTimestamp("starts_at").toInstant(),rs.getTimestamp("ends_at").toInstant(),rs.getString("time_zone"),rs.getBoolean("sync_to_google"),rs.getString("google_calendar_id"),rs.getString("google_event_id"), rs.getString("sync_status"), rs.getString("sync_error"), rs.getObject("sync_actor_id", UUID::class.java), rs.getString("google_etag"), rs.getLong("revision"), rs.getBoolean("pending_deletion"))
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
        return createEvent(actor, body).also { audit(actor, "calendar.event.created", it.id) }
    }
    @Transactional
    fun update(actor: UUID, id: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent {
        rbac.authorizeMutation(actor, "calendar:update")
        val owner = rbac.workspace(actor)
        val previous = repository.lockedFind(owner, id) ?: throw CalendarEventNotFound()
        if (previous.syncActorId != null && previous.syncActorId != actor) throw dev.kyrion.core.security.ForbiddenException()
        if ((previous.pendingDeletion || previous.syncStatus == "conflict") && body.syncToGoogle != false) throw CalendarSyncConflict()
        if (body.revision != null && body.revision != previous.revision) throw CalendarSyncConflict()
        repository.update(owner, id, body) ?: throw CalendarEventNotFound()
        repository.configureSync(owner, id, actor, body, previous)
        val result = repository.find(owner, id)!!
        audit(actor, "calendar.event.updated", id)
        return result
    }
    @Transactional
    fun delete(actor: UUID, id: UUID, revision: Long? = null) {
        rbac.authorizeMutation(actor, "calendar:delete")
        val owner = rbac.workspace(actor)
        val previous = repository.lockedFind(owner, id) ?: throw CalendarEventNotFound()
        if (previous.syncActorId != null && previous.syncActorId != actor) throw dev.kyrion.core.security.ForbiddenException()
        if (revision != null && revision != previous.revision) throw CalendarSyncConflict()
        if (previous.syncActorId != null) repository.markDeletion(owner, id) else repository.delete(owner, id)
        audit(actor, "calendar.event.deleted", id)
    }
    private fun createEvent(actor: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent {
        val owner = rbac.workspace(actor)
        val event = repository.save(owner, body)
        repository.configureSync(owner, event.id, actor, body, null)
        return repository.find(owner, event.id)!!
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
    @DeleteMapping("/{id}") fun delete(@PathVariable id: UUID, @RequestParam(required = false) revision: Long?, request: HttpServletRequest) = service.delete(request.authenticatedUserId(), id, revision)
}
@ResponseStatus(HttpStatus.NOT_FOUND)
class CalendarEventNotFound: RuntimeException()
@ResponseStatus(HttpStatus.BAD_REQUEST)
class InvalidCalendarEvent: RuntimeException()

@RestControllerAdvice
class CalendarErrorHandler {
    @ExceptionHandler(CalendarSyncBusy::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun busy() = mapOf("code" to "CALENDAR_SYNC_BUSY_OR_BACKOFF")
    @ExceptionHandler(CalendarSyncConflict::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun conflict() = mapOf("code" to "CALENDAR_SYNC_CONFLICT")
    @ExceptionHandler(InvalidCalendarEvent::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = mapOf("code" to "CALENDAR_EVENT_INVALID")
}

@ResponseStatus(HttpStatus.CONFLICT)
class CalendarSyncConflict : RuntimeException()
