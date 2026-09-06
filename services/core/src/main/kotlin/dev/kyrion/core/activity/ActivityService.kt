package dev.kyrion.core.activity

import org.springframework.stereotype.Service
import java.time.Clock
import java.util.UUID

@Service
class ActivityService(
    private val repository: ActivityEventRepository,
    private val clock: Clock = Clock.systemUTC(),
    private val actors: ActivityActorSource = ActivityActorSource { null },
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
        ownerId: UUID? = null,
    ): ActivityEvent = repository.append(
        ActivityEvent(
            id = UUID.randomUUID(),
            occurredAt = clock.instant(),
            category = category,
            eventType = eventType,
            status = status,
            actorType = actorType,
            actorId = if (actorType == ActivityActorType.USER) actors.currentActorId() ?: actorId else actorId,
            source = source,
            correlationId = correlationId,
            summaryCode = summaryCode,
            ownerId = ownerId ?: actorId?.takeIf { actorType == ActivityActorType.USER }
                ?.let { value: String -> runCatching<UUID> { UUID.fromString(value) }.getOrNull() },
        ),
    )

    fun recent(limit: Int): List<ActivityEvent> = repository.findRecent(limit)
    fun recent(ownerId: UUID, limit: Int): List<ActivityEvent> = repository.findRecentForOwner(ownerId, limit)
    fun timeline(ownerId: UUID, correlationId: UUID) = repository.findByCorrelation(ownerId, correlationId)
        .filter { it.ownerId == ownerId }.map(::safeTimelineEvent)
}

internal fun safeTimelineEvent(event: ActivityEvent): ActivityEvent {
    val legacyCapability = mapOf(
        "integration.nanoleaf.power" to "power.set", "integration.nanoleaf.brightness" to "light.setBrightness",
        "integration.nanoleaf.color" to "light.setColour",
    )[event.eventType]
    // Reuse safe facts from existing direct-control audit rows without rewriting their seals.
    if (legacyCapability != null) {
        val type = when (event.status) {
            ActivityStatus.CONFIRMED, ActivityStatus.PROPOSED -> "action.adapter.invoked"
            ActivityStatus.SUCCEEDED -> "action.adapter.completed"
            else -> "action.adapter.failed"
        }
        val code = when (event.status) {
            ActivityStatus.CONFIRMED, ActivityStatus.PROPOSED -> legacyCapability
            ActivityStatus.SUCCEEDED -> "action.succeeded"
            else -> "adapter.failed"
        }
        return safeTimelineEvent(event.copy(eventType = type, summaryCode = code, source = "nanoleaf"))
    }
    val uuid = Regex("[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
    val codes = setOf("action.proposed", "action.succeeded", "action.partially_succeeded", "action.failed", "action.denied",
        "action.unsupported", "action.confirmation_required", "target.not_found", "target.ambiguous", "proposal.invalid",
        "proposal.unavailable", "device.offline", "adapter.offline", "adapter.timeout", "adapter.failed", "adapter.invalid_result",
        "session.stale", "routine", "read", "power.set", "light.setBrightness", "light.setColour")
    val stages = setOf("action.proposed", "action.capability", "action.policy.accepted", "action.target.resolved",
        "action.adapter.invoked", "action.device.confirmed", "action.adapter.failed", "action.adapter.completed", "action.completed", "action.rejected",
        "action.confirmation_required", "action.request.received")
    return event.copy(eventType = event.eventType.takeIf { it in stages } ?: "activity.recorded",
        summaryCode = event.summaryCode.takeIf { it in codes || it.matches(uuid) } ?: "diagnostic.unavailable",
        source = event.source.takeIf { it in setOf("web", "voice", "automation", "integration", "mobile", "kyrion-core", "kyrion-gateway", "nanoleaf", "zigbee", "bluetooth", "home_assistant") } ?: "unknown",
        actorId = event.actorId?.takeIf { it.matches(uuid) })
}
