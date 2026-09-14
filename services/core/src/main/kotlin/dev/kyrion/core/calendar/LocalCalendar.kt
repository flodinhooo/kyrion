package dev.kyrion.core.calendar

import dev.kyrion.core.security.workspaceOwnerId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.web.bind.annotation.*
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.sql.Timestamp
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

data class LocalCalendarEvent(val id: UUID, val title: String, val description: String?, val startsAt: Instant, val endsAt: Instant, val timeZone: String, val syncToGoogle: Boolean, val googleCalendarId: String? = null, val googleEventId: String? = null)
data class LocalCalendarEventRequest(val title: String, val description: String? = null, val startsAt: Instant, val endsAt: Instant, val timeZone: String = "UTC", val syncToGoogle: Boolean = false)

@org.springframework.stereotype.Repository
class LocalCalendarRepository(private val jdbc: JdbcClient) {
    fun findAll(owner: UUID): List<LocalCalendarEvent> = jdbc.sql("SELECT * FROM local_calendar_event WHERE owner_id=:owner ORDER BY starts_at, title").param("owner", owner).query { rs, _ -> map(rs) }.list()
    fun find(owner: UUID, id: UUID): LocalCalendarEvent? = jdbc.sql("SELECT * FROM local_calendar_event WHERE owner_id=:owner AND id=:id").param("owner", owner).param("id", id).query { rs, _ -> map(rs) }.optional().orElse(null)
    fun save(owner: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent { require(body.title.isNotBlank() && body.endsAt.isAfter(body.startsAt)) { "Invalid calendar event" }; val id=UUID.randomUUID(); val now=Timestamp.from(Instant.now()); jdbc.sql("INSERT INTO local_calendar_event(id,owner_id,title,description,starts_at,ends_at,time_zone,content_fingerprint,sync_to_google,created_at,updated_at) VALUES(:id,:owner,:title,:description,:startsAt,:endsAt,:timeZone,:fingerprint,:sync,:created,:updated)").param("id",id).param("owner",owner).param("title",body.title.trim()).param("description",body.description).param("startsAt",Timestamp.from(body.startsAt)).param("endsAt",Timestamp.from(body.endsAt)).param("timeZone",body.timeZone).param("fingerprint",fingerprint(owner,body)).param("sync",body.syncToGoogle).param("created",now).param("updated",now).update(); return find(owner,id)!! }
    fun update(owner: UUID, id: UUID, body: LocalCalendarEventRequest): LocalCalendarEvent? { require(body.title.isNotBlank() && body.endsAt.isAfter(body.startsAt)) { "Invalid calendar event" }; val count=jdbc.sql("UPDATE local_calendar_event SET title=:title,description=:description,starts_at=:startsAt,ends_at=:endsAt,time_zone=:timeZone,content_fingerprint=:fingerprint,sync_to_google=:sync,updated_at=:updated WHERE owner_id=:owner AND id=:id").param("owner",owner).param("id",id).param("title",body.title.trim()).param("description",body.description).param("startsAt",Timestamp.from(body.startsAt)).param("endsAt",Timestamp.from(body.endsAt)).param("timeZone",body.timeZone).param("fingerprint",fingerprint(owner,body)).param("sync",body.syncToGoogle).param("updated",Timestamp.from(Instant.now())).update(); return if(count==1) find(owner,id) else null }
    fun delete(owner: UUID,id: UUID)=jdbc.sql("DELETE FROM local_calendar_event WHERE owner_id=:owner AND id=:id").param("owner",owner).param("id",id).update()==1
    private fun fingerprint(owner: UUID,b: LocalCalendarEventRequest)=MessageDigest.getInstance("SHA-256").digest("$owner|${b.title.trim()}|${b.startsAt}|${b.endsAt}|${b.timeZone}".toByteArray(StandardCharsets.UTF_8)).joinToString(""){ "%02x".format(it) }
    private fun map(rs: java.sql.ResultSet)=LocalCalendarEvent(rs.getObject("id",UUID::class.java),rs.getString("title"),rs.getString("description"),rs.getTimestamp("starts_at").toInstant(),rs.getTimestamp("ends_at").toInstant(),rs.getString("time_zone"),rs.getBoolean("sync_to_google"),rs.getString("google_calendar_id"),rs.getString("google_event_id"))
}

@RestController
@RequestMapping("/v1/calendar/events")
class LocalCalendarController(private val repository: LocalCalendarRepository) {
    @GetMapping fun all(request: HttpServletRequest)=repository.findAll(request.workspaceOwnerId())
    @PostMapping fun create(@RequestBody body: LocalCalendarEventRequest, request: HttpServletRequest)=repository.save(request.workspaceOwnerId(),body)
    @PutMapping("/{id}") fun update(@PathVariable id: UUID,@RequestBody body: LocalCalendarEventRequest,request: HttpServletRequest)=repository.update(request.workspaceOwnerId(),id,body) ?: throw CalendarEventNotFound()
    @DeleteMapping("/{id}") fun delete(@PathVariable id: UUID,request: HttpServletRequest){if(!repository.delete(request.workspaceOwnerId(),id)) throw CalendarEventNotFound()}
}
class CalendarEventNotFound: RuntimeException()
