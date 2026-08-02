package dev.kyrion.core.activity

import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

class ActivityServiceTest {
    private val repository = InMemoryActivityEventRepository()
    private val now = Instant.parse("2026-08-02T12:00:00Z")
    private val service = ActivityService(repository, Clock.fixed(now, ZoneOffset.UTC))

    @Test
    fun `records a data-minimised event with a correlation id`() {
        val correlationId = UUID.randomUUID()

        val event = service.record(
            category = ActivityCategory.SYSTEM,
            eventType = "core.started",
            status = ActivityStatus.SUCCEEDED,
            actorType = ActivityActorType.SYSTEM,
            source = "kyrion-core",
            summaryCode = "activity.core.started",
            correlationId = correlationId,
        )

        assertThat(event.occurredAt).isEqualTo(now)
        assertThat(event.correlationId).isEqualTo(correlationId)
        assertThat(event.actorId).isNull()
        assertThat(repository.events).containsExactly(event)
    }

    @Test
    fun `delegates the requested recent event limit`() {
        service.recent(25)

        assertThat(repository.lastLimit).isEqualTo(25)
    }
}

private class InMemoryActivityEventRepository : ActivityEventRepository {
    val events = mutableListOf<ActivityEvent>()
    var lastLimit: Int? = null

    override fun append(event: ActivityEvent): ActivityEvent = event.also(events::add)

    override fun findRecent(limit: Int): List<ActivityEvent> {
        lastLimit = limit
        return events.take(limit)
    }
}
