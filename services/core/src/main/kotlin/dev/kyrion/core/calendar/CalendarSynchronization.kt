package dev.kyrion.core.calendar

import dev.kyrion.core.integration.*
import dev.kyrion.core.security.RbacService
import dev.kyrion.core.security.authenticatedUserId
import dev.kyrion.core.activity.*
import jakarta.servlet.http.HttpServletRequest
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.*
import java.util.UUID

data class CalendarSyncResult(val synchronized: Int, val conflicts: Int, val failed: Int, val correlationId: UUID, val errorCode: String? = null, val retryAfterSeconds: Long? = null)

@Service
class CalendarSynchronization(
    private val repository: LocalCalendarRepository,
    private val google: GoogleIntegrationService,
    private val rbac: RbacService,
    private val activity: ActivityService,
) {
    // Single local Core runtime; conditional provider writes and stable IDs also
    // protect retries and competing runtimes. Never hold a DB transaction over HTTP.
    @Synchronized
    fun sync(actor: UUID, automatic: Boolean = false, heartbeat: () -> Unit = {}): CalendarSyncResult {
        listOf("calendar:read", "calendar:create", "calendar:update", "calendar:delete").forEach { rbac.require(actor, it) }
        val owner = rbac.workspace(actor)
        val events = repository.findAll(owner).filter { it.syncToGoogle && it.syncActorId == actor }
        val correlation = UUID.randomUUID()
        var synchronized = 0; var conflicts = 0; var failed = 0
        var errorCode: String? = null
        var retryAfter: Long? = null
        var rateLimited = false
        val calendars = if (events.isNotEmpty()) google.calendars(actor).items.associateBy { it.id } else emptyMap()
        events.forEach { event ->
            if(rateLimited) return@forEach
            heartbeat()
            // A long batch must observe permission revocation between events.
            listOf("calendar:read", "calendar:create", "calendar:update", "calendar:delete").forEach { rbac.require(actor, it) }
            if (event.syncStatus == "conflict") { conflicts++; return@forEach }
            val calendar = event.googleCalendarId ?: return@forEach
            if (calendars[calendar]?.accessRole !in setOf("owner", "writer")) {
                repository.syncOutcome(owner, event, failureStatus(event), "CALENDAR_NOT_WRITABLE"); failed++; errorCode = "CALENDAR_NOT_WRITABLE"; return@forEach
            }
            record(actor, owner, event.id, correlation, automatic, ActivityStatus.PROPOSED)
            try {
                synchronize(owner, actor, event)
                synchronized++
                record(actor, owner, event.id, correlation, automatic, ActivityStatus.SUCCEEDED)
            } catch (_: CalendarSyncConflict) {
                repository.syncOutcome(owner, event, "conflict", "CALENDAR_SYNC_CONFLICT"); conflicts++
                record(actor, owner, event.id, correlation, automatic, ActivityStatus.FAILED)
            } catch (error: GoogleProviderException) {
                val conflict = error.status in setOf(404, 409, 410, 412)
                repository.syncOutcome(owner, event, if (conflict) "conflict" else failureStatus(event),
                    if (conflict) "CALENDAR_SYNC_CONFLICT" else if (error.status == 429) "GOOGLE_RATE_LIMITED" else "GOOGLE_UNAVAILABLE")
                if (conflict) conflicts++ else { rateLimited=error.status==429; failed++; errorCode = if(error.status==429) "GOOGLE_RATE_LIMITED" else "GOOGLE_UNAVAILABLE"; retryAfter=maxOf(retryAfter ?: 0,error.retryAfterSeconds ?: 0) }
                record(actor, owner, event.id, correlation, automatic, ActivityStatus.FAILED)
            } catch (_: Exception) {
                repository.syncOutcome(owner, event, failureStatus(event), "GOOGLE_UNAVAILABLE"); failed++; errorCode="GOOGLE_UNAVAILABLE"
                record(actor, owner, event.id, correlation, automatic, ActivityStatus.FAILED)
            }
        }
        return CalendarSyncResult(synchronized, conflicts, failed, correlation, errorCode, retryAfter)
    }

    private fun synchronize(owner: UUID, actor: UUID, local: LocalCalendarEvent) {
        val calendar = local.googleCalendarId ?: throw CalendarSyncConflict()
        val id = local.googleEventId ?: throw CalendarSyncConflict()
        val remote = try { google.remoteEvent(actor, calendar, id) } catch (error: GoogleProviderException) {
            if (error.status !in setOf(404,410)) throw error
            null
        }
        val remoteMissing = remote == null || remote.status == "cancelled"
        if (local.pendingDeletion) {
            if (!remoteMissing) {
                if (remote!!.etag != local.googleEtag || local.googleEtag == null) throw CalendarSyncConflict()
                google.removeEvent(actor, calendar, id, local.googleEtag)
            }
            repository.completeDeletion(owner, local)
            return
        }
        if (local.googleEtag == null) {
            val created = if (remote == null) {
                // Google accepts client-generated base32hex IDs. Repeating an
                // uncertain insert can never create a second remote event.
                google.createEvent(actor, request(local).copy(id = id))
            } else {
                if (remote.kyrionId != id || remote.status == "cancelled" || !matches(local, remote)) throw CalendarSyncConflict()
                remote
            }
            val etag = created.etag ?: throw CalendarSyncConflict()
            // Recover only matching inserts; divergent remote data is a conflict.
            repository.syncOutcome(owner, local, "synced", null, etag)
            return
        }
        if (remoteMissing || remote!!.recurring || remote.etag == null) throw CalendarSyncConflict()
        if (local.syncStatus in setOf("synced", "read_error")) {
            if (remote.etag != local.googleEtag) repository.acceptRemote(owner, local, remote)
            else repository.syncOutcome(owner, local, "synced", null)
            return
        }
        if (remote.etag != local.googleEtag) throw CalendarSyncConflict()
        val updated = google.patchEvent(actor, id, request(local), local.googleEtag)
        repository.syncOutcome(owner, local, "synced", null, updated.etag ?: throw CalendarSyncConflict())
    }

    private fun failureStatus(event: LocalCalendarEvent) = if(event.syncStatus in setOf("synced", "read_error")) "read_error" else "error"

    private fun matches(local: LocalCalendarEvent, remote: GoogleCalendarEvent) =
        local.title == remote.summary && (local.description ?: "") == (remote.description ?: "") &&
            runCatching { java.time.OffsetDateTime.parse(remote.start).toInstant() == local.startsAt &&
                java.time.OffsetDateTime.parse(remote.end).toInstant() == local.endsAt }.getOrDefault(false)

    private fun request(local: LocalCalendarEvent) = GoogleCalendarEventRequest(
        local.googleCalendarId!!, local.title, local.startsAt.toString(), local.endsAt.toString(), local.description)

    private fun record(actor: UUID, owner: UUID, event: UUID, correlation: UUID, automatic: Boolean, status: ActivityStatus) = activity.record(
        ActivityCategory.INTEGRATION, "calendar.event.synchronized", status, if(automatic) ActivityActorType.SYSTEM else ActivityActorType.USER,
        "kyrion-core", event.toString(), actor.toString(), correlation, owner)
}

@RestController
class CalendarSyncController(private val service: CalendarSyncRunner) {
    @PostMapping("/v1/calendar/sync")
    fun sync(request: HttpServletRequest) = service.run(request.authenticatedUserId())
}
