package dev.kyrion.core.calendar

import dev.kyrion.core.activity.*
import dev.kyrion.core.integration.*
import dev.kyrion.core.security.ForbiddenException
import dev.kyrion.core.security.RbacService
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import org.springframework.transaction.support.TransactionTemplate
import java.time.Instant
import java.util.UUID

private data class DeliveryAttempt(val space: UUID, val actor: UUID, val event: HouseholdCalendarEvent, val grant: DestinationGrant, val row: DeliveryRow)

@Service
class HouseholdCalendarDelivery(
    private val repository: HouseholdDeliveryRepository, private val calendars: HouseholdCalendarRepository,
    private val connections: CalendarDisclosureRepository, private val rbac: RbacService,
    private val google: GoogleIntegrationService, private val transactions: TransactionTemplate, private val activity: ActivityService,
) {
    fun setting(actor: UUID): HouseholdDestinationSetting = transaction {
        val space = readSpace(actor)
        setting(repository.latest(space).find { it.user == actor })
    }
    fun change(actor: UUID, body: HouseholdDestinationChange): HouseholdDestinationSetting {
        if (body.revision < 0 || body.calendarId?.let { it.isBlank() || it.length > 512 || it == "primary" } == true) invalid()
        val before = transaction {
            readSpace(actor); rbac.require(actor, "calendar:update")
            if (body.calendarId != null) {
                rbac.require(actor, "calendar:create")
                connections.connection(actor) ?: unavailable()
            } else UUID(0, 0)
        }
        if (body.calendarId != null && google.calendars(actor).items.none { it.id == body.calendarId && it.accessRole in setOf("owner", "writer") }) invalid()
        return transaction {
            val space = requireHome(rbac.authorizeMutation(actor, "calendar:update")); rbac.require(actor, "calendar:read")
            val old = repository.latest(space).find { it.user == actor }
            if ((old?.revision ?: 0) != body.revision) conflict()
            if (body.calendarId != null) {
                rbac.require(actor, "calendar:create")
                if (connections.connection(actor) != before) unavailable()
                if (old?.active == true && old.connection == before && old.calendar == body.calendarId) return@transaction setting(old)
            }
            val id = repository.change(space, actor, if (body.calendarId == null) null else before, body.calendarId, body.revision + 1)
            audit(space, actor, id, UUID.randomUUID(), "calendar.destination.changed", ActivityStatus.SUCCEEDED)
            setting(repository.grant(space, id))
        }
    }

    fun view(actor: UUID, eventId: UUID): HouseholdDeliveries = transaction {
        val space = readSpace(actor)
        val event = editableEvent(actor, space, eventId)
        view(space, event)
    }

    fun deliver(actor: UUID, eventId: UUID, body: HouseholdDeliveryRequest): HouseholdDeliveryView {
        if (body.revision < 0) invalid()
        val attempt = transaction {
            val space = requireHome(rbac.authorizeMutation(actor, "calendar:update")); rbac.require(actor, "calendar:read")
            val event = editableEvent(actor, space, eventId, true)
            if (event.revision != body.revision) conflict()
            val grant = repository.grant(space, body.targetId) ?: unavailable()
            requireGrant(space, event, grant)
            val row = repository.reserve(space, eventId, grant)
            audit(space, actor, row.id, row.attempt, "calendar.delivery.attempt", ActivityStatus.PROPOSED)
            DeliveryAttempt(space, actor, event, grant, row)
        }
        var writeIssued = false
        val guard = { transaction { authorize(attempt); Unit } }
        try {
            val grant = attempt.grant
            val row = attempt.row
            val remote = try { google.deliveryEvent(grant.user, grant.connection!!, grant.calendar!!, row.remoteId, guard) }
                catch (error: GoogleProviderException) { if (error.status in setOf(404, 410)) null else throw error }
            val desired = GoogleCalendarEventRequest(grant.calendar!!, attempt.event.title, attempt.event.startsAt.toString(),
                attempt.event.endsAt.toString(), attempt.event.description, id = row.remoteId)
            val result = when {
                remote == null -> {
                    if (row.writeStarted || row.deliveredRevision != null) reviewConflict()
                    writeIntent(attempt); writeIssued = true
                    google.createDelivery(grant.user, grant.connection!!, desired, guard)
                }
                else -> {
                    requireCopy(remote, row)
                    if (matches(attempt.event, remote)) remote
                    else {
                        if (row.etag == null || remote.etag != row.etag) reviewConflict()
                        writeIntent(attempt); writeIssued = true
                        google.patchDelivery(grant.user, grant.connection!!, row.remoteId, desired.copy(id = null), row.etag, guard)
                    }
                }
            }
            requireCopy(result, attempt.row)
            if (!matches(attempt.event, result)) reviewConflict()
            transaction {
                authorize(attempt)
                if (!repository.finish(attempt.space, attempt.row, "SYNCED", null, attempt.event.revision, result.etag)) busy()
                audit(attempt.space, actor, attempt.row.id, attempt.row.attempt, "calendar.delivery.attempt", ActivityStatus.SUCCEEDED)
                Unit
            }
        } catch (error: Exception) {
            val definiteDenial = error is GoogleProviderException && error.status in setOf(400, 401, 403, 429)
            val authority = error is ForbiddenException || error is GoogleDisconnectedException || error is GoogleCapabilityDisabledException ||
                error is GoogleReauthorizationException || (error is HouseholdDeliveryFailure && error.code in setOf("CALENDAR_DELIVERY_UNAVAILABLE", "CALENDAR_DELIVERY_STALE"))
            val conflict = error is GoogleReadOnlyEventException || (error is GoogleProviderException && error.status in setOf(404, 409, 410, 412)) ||
                (error is HouseholdDeliveryFailure && error.code == "CALENDAR_DELIVERY_CONFLICT")
            val state = when { authority && writeIssued -> "NEEDS_REVIEW"; authority -> "BLOCKED"; conflict -> "CONFLICT";
                definiteDenial -> "ERROR"; writeIssued -> "NEEDS_REVIEW"; else -> "ERROR" }
            val code = when { authority -> "CALENDAR_DELIVERY_AUTHORITY_CHANGED"; conflict -> "CALENDAR_DELIVERY_CONFLICT";
                error is GoogleProviderException && error.status == 429 -> "GOOGLE_RATE_LIMITED";
                definiteDenial -> "CALENDAR_DELIVERY_PROVIDER_DENIED"; writeIssued -> "CALENDAR_DELIVERY_UNCERTAIN"; else -> "CALENDAR_DELIVERY_PROVIDER_ERROR" }
            transaction {
                // Recording the result of an already accepted attempt must still work
                // after withdrawal. Never use this path to authorize another HTTP call.
                repository.lock(attempt.space)
                if (definiteDenial && !attempt.row.writeStarted) repository.clearDefinitivelyDeniedInsert(attempt.space, attempt.row)
                if (!repository.finish(attempt.space, attempt.row, state, code, null, null)) busy()
                audit(attempt.space, actor, attempt.row.id, attempt.row.attempt, "calendar.delivery.attempt", ActivityStatus.FAILED)
                Unit
            }
        }
        return transaction {
            val space = readSpace(actor)
            val event = editableEvent(actor, space, eventId)
            view(space, event).items.firstOrNull { it.id == attempt.row.id } ?: unavailable()
        }
    }

    private fun writeIntent(attempt: DeliveryAttempt) = transaction {
        authorize(attempt)
        repository.writeStarted(attempt.space, attempt.row)
        audit(attempt.space, attempt.actor, attempt.row.id, attempt.row.attempt, "calendar.delivery.write", ActivityStatus.PROPOSED)
        Unit
    }
    private fun authorize(attempt: DeliveryAttempt) {
        val space = requireHome(rbac.authorizeMutation(attempt.actor, "calendar:update")); rbac.require(attempt.actor, "calendar:read")
        if (space != attempt.space) throw ForbiddenException()
        val event = editableEvent(attempt.actor, space, attempt.event.id)
        if (event.revision != attempt.event.revision) throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_STALE", HttpStatus.CONFLICT)
        val grant = repository.grant(space, attempt.grant.id) ?: unavailable()
        if (grant != attempt.grant) unavailable()
        requireGrant(space, event, grant)
        if (!repository.current(space, attempt.row)) busy()
    }
    private fun requireGrant(space: UUID, event: HouseholdCalendarEvent, grant: DestinationGrant) {
        if (!grant.active || grant.connection == null || grant.calendar == null || grant.space != space || grant.user !in event.participantIds ||
            connections.connection(grant.user) != grant.connection) unavailable()
        listOf("calendar:read", "calendar:create", "calendar:update").forEach { rbac.require(grant.user, it) }
        if (rbac.workspace(grant.user) != space) unavailable()
    }
    private fun editableEvent(actor: UUID, space: UUID, id: UUID, lock: Boolean = false): HouseholdCalendarEvent {
        rbac.require(actor, "calendar:update")
        val event = calendars.find(space, id, lock) ?: unavailable()
        if (actor !in event.participantIds) throw ForbiddenException()
        return event
    }
    private fun view(space: UUID, event: HouseholdCalendarEvent): HouseholdDeliveries {
        val grants = repository.latest(space).associateBy { it.user }
        val targets = calendars.members(space).filter { it.id in event.participantIds }.map { member ->
            val grant = grants[member.id]
            val eligible = if (grant == null) false else try { requireGrant(space, event, grant); true } catch (_: ForbiddenException) { false } catch (_: HouseholdDeliveryFailure) { false }
            HouseholdDeliveryTarget(member.id, member.username, if (eligible) grant?.id else null)
        }
        val names = calendars.members(space).associate { it.id to it.username }
        val items = repository.rows(space, event.id).map { row ->
            val grant = repository.grant(space, row.grant)
            val available = if (grant == null) false else try { requireGrant(space, event, grant); true } catch (_: ForbiddenException) { false } catch (_: HouseholdDeliveryFailure) { false }
            val state = when { row.state == "RUNNING" && !row.busy -> "NEEDS_REVIEW"; row.state == "RUNNING" -> "RUNNING";
                row.state == "NEEDS_REVIEW" -> "NEEDS_REVIEW";
                !available -> "BLOCKED"; row.state == "SYNCED" && row.deliveredRevision != event.revision -> "OUTDATED"; else -> row.state }
            HouseholdDeliveryView(row.id, row.user, names[row.user], state, row.deliveredRevision,
                if (!available) "CALENDAR_DELIVERY_AUTHORITY_CHANGED" else row.errorCode)
        }
        return HouseholdDeliveries(event.revision, targets, items)
    }
    private fun setting(grant: DestinationGrant?) = HouseholdDestinationSetting(grant?.id, grant?.calendar,
        grant?.active == true && grant.connection != null && connections.connection(grant.user) == grant.connection, grant?.revision ?: 0)
    private fun requireCopy(remote: GoogleCalendarEvent, row: DeliveryRow) {
        if (remote.id != row.remoteId || remote.kyrionId != row.remoteId || remote.status == "cancelled" || remote.recurring ||
            remote.start == null || remote.end == null || remote.start.length == 10 || remote.end.length == 10 ||
            remote.etag.isNullOrBlank() || remote.etag.length > 512 || remote.etag.any { it == '\r' || it == '\n' }) reviewConflict()
    }
    private fun matches(event: HouseholdCalendarEvent, remote: GoogleCalendarEvent) = event.title == remote.summary &&
        (event.description ?: "") == (remote.description ?: "") && runCatching {
            Instant.parse(remote.start) == event.startsAt && Instant.parse(remote.end) == event.endsAt
        }.getOrDefault(false)
    private fun readSpace(actor: UUID): UUID { rbac.require(actor, "calendar:read"); return requireHome(rbac.workspace(actor)) }
    private fun requireHome(space: UUID): UUID { if (!connections.home(space)) throw ForbiddenException(); return space }
    private fun audit(space: UUID, actor: UUID, target: UUID, correlation: UUID, type: String, status: ActivityStatus) =
        activity.record(ActivityCategory.INTEGRATION, type, status, ActivityActorType.USER, "kyrion-core", target.toString(), actor.toString(), correlation, space)
    private fun <T : Any> transaction(action: () -> T): T = transactions.execute { action() }
    private fun invalid(): Nothing = throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_INVALID", HttpStatus.BAD_REQUEST)
    private fun unavailable(): Nothing = throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_UNAVAILABLE", HttpStatus.NOT_FOUND)
    private fun conflict(): Nothing = throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_STALE", HttpStatus.CONFLICT)
    private fun reviewConflict(): Nothing = throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_CONFLICT", HttpStatus.CONFLICT)
    private fun busy(): Nothing = throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_BUSY", HttpStatus.CONFLICT)
}

class HouseholdDeliveryFailure(val code: String, val status: HttpStatus) : RuntimeException(code)
