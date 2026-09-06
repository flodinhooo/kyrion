package dev.kyrion.core.activity

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.time.Instant
import java.util.UUID

class ActionTimelineTest {
    @Test
    fun `existing direct Nanoleaf control audit remains understandable without exposing raw provider text`() {
        val event = ActivityEvent(UUID.randomUUID(), Instant.now(), ActivityCategory.INTEGRATION, "integration.nanoleaf.power",
            ActivityStatus.FAILED, ActivityActorType.USER, UUID.randomUUID().toString(), "kyrion-core", UUID.randomUUID(), "nanoleaf.power.failed", UUID.randomUUID())
        val projected = safeTimelineEvent(event)
        assertEquals("action.adapter.failed", projected.eventType)
        assertEquals("adapter.failed", projected.summaryCode)
        assertEquals("nanoleaf", projected.source)
        assertEquals("integration.nanoleaf.power", event.eventType)
    }

    @Test
    fun `timeline projection redacts arbitrary provider text while preserving bounded diagnostic codes`() {
        val event = ActivityEvent(
            UUID.randomUUID(),
            Instant.now(),
            ActivityCategory.CAPABILITY,
            "provider.private-payload",
            ActivityStatus.FAILED,
            ActivityActorType.INTEGRATION,
            "private-token",
            "private-address",
            UUID.randomUUID(),
            "secret=token",
            UUID.randomUUID()
        )
        val safe = safeTimelineEvent(event)
        assertEquals("activity.recorded", safe.eventType)
        assertEquals("diagnostic.unavailable", safe.summaryCode)
        assertEquals("unknown", safe.source)
        assertNull(safe.actorId)
        for (reason in listOf(
            "target.not_found",
            "target.ambiguous",
            "action.unsupported",
            "action.denied",
            "adapter.offline",
            "adapter.timeout",
            "device.offline",
            "adapter.invalid_result",
            "action.partially_succeeded",
            "session.stale"
        )) {
            assertEquals(reason, safeTimelineEvent(event.copy(summaryCode = reason)).summaryCode)
        }
    }
}
