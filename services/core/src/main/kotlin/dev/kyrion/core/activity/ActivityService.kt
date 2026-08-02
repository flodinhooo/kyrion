package dev.kyrion.core.activity

import org.springframework.stereotype.Service
import java.time.Clock
import java.util.UUID

@Service
class ActivityService(
    private val repository: ActivityEventRepository,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun record(
        category: ActivityCategory,
        eventType: String,
        status: ActivityStatus,
        actorType: ActivityActorType,
        source: String,
        summaryCode: String,
        actorId: String? = null,
        correlationId: UUID = UUID.randomUUID(),
    ): ActivityEvent = repository.append(
        ActivityEvent(
            id = UUID.randomUUID(),
            occurredAt = clock.instant(),
            category = category,
            eventType = eventType,
            status = status,
            actorType = actorType,
            actorId = actorId,
            source = source,
            correlationId = correlationId,
            summaryCode = summaryCode,
        ),
    )

    fun recent(limit: Int): List<ActivityEvent> = repository.findRecent(limit)
}
