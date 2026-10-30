package dev.kyrion.core.calendar

import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.integration.*
import dev.kyrion.core.security.*
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.mockito.Mockito.*
import java.time.Instant
import java.util.UUID

class CalendarSynchronizationTest {
    private val actor = UUID.randomUUID()
    private val owner = UUID.randomUUID()
    private val repository = mock(LocalCalendarRepository::class.java)
    private val google = mock(GoogleIntegrationService::class.java)
    private val rbac = mock(RbacService::class.java)
    private val activity = mock(ActivityService::class.java)
    private val service = CalendarSynchronization(repository, google, rbac, activity)
    private val local = LocalCalendarEvent(UUID.randomUUID(), "Appointment", null,
        Instant.parse("2026-10-19T09:00:00Z"), Instant.parse("2026-10-19T10:00:00Z"), "Europe/Zurich", true,
        "selected-calendar", "abc123", "pending", syncActorId = actor)
    private val remote = GoogleCalendarEvent("abc123", "Appointment", "2026-10-19T11:00:00+02:00", "2026-10-19T12:00:00+02:00", "v1", kyrionId = "abc123")

    private fun setup(event: LocalCalendarEvent = local) {
        `when`(rbac.workspace(actor)).thenReturn(owner)
        `when`(repository.findAll(owner)).thenReturn(listOf(event))
        `when`(google.calendars(actor)).thenReturn(GoogleCalendars(listOf(GoogleCalendar("selected-calendar", "Selected", "Europe/Zurich", "writer"))))
    }

    @Test fun `insert targets explicit calendar with stable ID and can recover an uncertain successful insert`() {
        setup()
        `when`(google.remoteEvent(actor, "selected-calendar", "abc123")).thenThrow(GoogleProviderException(404))
        `when`(google.createEvent(actor, GoogleCalendarEventRequest("selected-calendar", local.title, local.startsAt.toString(), local.endsAt.toString(), null, "abc123"))).thenReturn(remote)
        assertEquals(1, service.sync(actor).synchronized)
        verify(repository).syncOutcome(owner, local, "synced", null, "v1")
        reset(google)
        setup()
        `when`(google.remoteEvent(actor, "selected-calendar", "abc123")).thenReturn(remote)
        assertEquals(1, service.sync(actor).synchronized)
        assertTrue(mockingDetails(google).invocations.none { it.method.name == "createEvent" })
    }

    @Test fun `remote changes import into a clean linked event without a write loop`() {
        val event = local.copy(googleEtag = "v1", syncStatus = "synced")
        setup(event)
        val changed = remote.copy(summary = "Changed remotely", etag = "v2")
        doReturn(changed).`when`(google).remoteEvent(actor, "selected-calendar", "abc123")
        assertEquals(1, service.sync(actor).synchronized)
        verify(repository).acceptRemote(owner, event, changed)
        assertTrue(mockingDetails(google).invocations.none { it.method.name == "patchEvent" })
    }

    @Test fun `retry of a failed clean read imports remote changes instead of exporting stale local data`() {
        val event = local.copy(googleEtag = "v1", syncStatus = "synced")
        setup(event)
        `when`(google.remoteEvent(actor, "selected-calendar", "abc123")).thenThrow(GoogleProviderException(503))
        assertEquals(1, service.sync(actor).failed)
        verify(repository).syncOutcome(owner, event, "read_error", "GOOGLE_UNAVAILABLE", "v1")
        val retry = event.copy(syncStatus = "read_error")
        setup(retry)
        val changed = remote.copy(etag = "v2", summary = "Changed during outage")
        doReturn(changed).`when`(google).remoteEvent(actor, "selected-calendar", "abc123")
        assertEquals(1, service.sync(actor).synchronized)
        verify(repository).acceptRemote(owner, retry, changed)
        assertTrue(mockingDetails(google).invocations.none { it.method.name == "patchEvent" })
    }

    @Test fun `local edits patch conditionally and update the remote version`() {
        val event = local.copy(googleEtag = "v1")
        setup(event)
        `when`(google.remoteEvent(actor, "selected-calendar", "abc123")).thenReturn(remote)
        val body = GoogleCalendarEventRequest("selected-calendar", local.title, local.startsAt.toString(), local.endsAt.toString())
        `when`(google.patchEvent(actor, "abc123", body, "v1")).thenReturn(remote.copy(etag = "v2"))
        assertEquals(1, service.sync(actor).synchronized)
        verify(repository).syncOutcome(owner, event, "synced", null, "v2")
    }

    @Test fun `competing modifications preserve data as a conflict`() {
        val event = local.copy(googleEtag = "v1")
        setup(event)
        `when`(google.remoteEvent(actor, "selected-calendar", "abc123")).thenReturn(remote.copy(etag = "v2"))
        assertEquals(1, service.sync(actor).conflicts)
        verify(repository).syncOutcome(owner, event, "conflict", "CALENDAR_SYNC_CONFLICT", "v1")
        assertTrue(mockingDetails(google).invocations.none { it.method.name == "patchEvent" || it.method.name == "removeEvent" })
    }

    @Test fun `remote cancellation keeps local copy as conflict instead of recreating or deleting it`() {
        val event = local.copy(googleEtag = "v1", syncStatus = "synced")
        setup(event)
        `when`(google.remoteEvent(actor, "selected-calendar", "abc123")).thenReturn(remote.copy(status = "cancelled"))
        assertEquals(1, service.sync(actor).conflicts)
        assertTrue(mockingDetails(repository).invocations.none { it.method.name == "delete" })
        assertTrue(mockingDetails(google).invocations.none { it.method.name == "createEvent" })
    }

    @Test fun `deletion uses selected calendar and version and only removes tombstone after confirmation`() {
        val event = local.copy(googleEtag = "v1", pendingDeletion = true)
        setup(event)
        `when`(google.remoteEvent(actor, "selected-calendar", "abc123")).thenReturn(remote)
        assertEquals(1, service.sync(actor).synchronized)
        verify(google).removeEvent(actor, "selected-calendar", "abc123", "v1")
        verify(repository).completeDeletion(owner, event)
    }

    @Test fun `rate limited deletion retains tombstone and retries safely`() {
        val event = local.copy(googleEtag = "v1", pendingDeletion = true)
        setup(event)
        `when`(google.remoteEvent(actor, "selected-calendar", "abc123")).thenReturn(remote)
        doThrow(GoogleProviderException(429)).doNothing().`when`(google).removeEvent(actor, "selected-calendar", "abc123", "v1")
        assertEquals(1, service.sync(actor).failed)
        verify(repository, never()).completeDeletion(owner, event)
        assertEquals(1, service.sync(actor).synchronized)
        verify(repository).completeDeletion(owner, event)
    }

    @Test fun `rate limit stops the batch and preserves provider retry after`() {
        val event = local.copy(googleEtag="v1")
        setup(event)
        `when`(repository.findAll(owner)).thenReturn(listOf(event,event.copy(id=UUID.randomUUID(),googleEventId="next")))
        `when`(google.remoteEvent(actor,"selected-calendar","abc123")).thenThrow(GoogleProviderException(429,120))
        val result=service.sync(actor)
        assertEquals("GOOGLE_RATE_LIMITED",result.errorCode)
        assertEquals(120L,result.retryAfterSeconds)
        verify(google,never()).remoteEvent(actor,"selected-calendar","next")
    }

    @Test fun `read only calendars and another users exports cannot be written`() {
        setup()
        `when`(google.calendars(actor)).thenReturn(GoogleCalendars(listOf(GoogleCalendar("selected-calendar", "Reader", null, "reader"))))
        assertEquals(1, service.sync(actor).failed)
        assertTrue(mockingDetails(google).invocations.none { it.method.name == "remoteEvent" })
        `when`(repository.findAll(owner)).thenReturn(listOf(local.copy(syncActorId = UUID.randomUUID()), local.copy(syncToGoogle = false)))
        assertEquals(0, service.sync(actor).synchronized)
    }

    @Test fun `permission denial precedes provider or repository access`() {
        doThrow(ForbiddenException()).`when`(rbac).require(actor, "calendar:delete")
        assertThrows<ForbiddenException> { service.sync(actor) }
        verifyNoInteractions(repository, google)
    }

    @Test fun `revocation during a batch prevents the next event from accessing Google`() {
        setup()
        assertThrows<ForbiddenException> {
            service.sync(actor, heartbeat = {
                doThrow(ForbiddenException()).`when`(rbac).require(actor, "calendar:update")
            })
        }
        verify(google, never()).remoteEvent(actor, "selected-calendar", "abc123")
        assertTrue(mockingDetails(google).invocations.none { it.method.name == "createEvent" })
    }

    @Test fun `divergent event found after uncertain insert is preserved as conflict`() {
        setup()
        `when`(google.remoteEvent(actor, "selected-calendar", "abc123")).thenReturn(remote.copy(summary = "Changed externally"))
        assertEquals(1, service.sync(actor).conflicts)
        assertTrue(mockingDetails(google).invocations.none { it.method.name == "patchEvent" })
    }
}
