package dev.kyrion.core.activity

import java.util.UUID

interface ActivityEventRepository {
    fun append(event: ActivityEvent): ActivityEvent

    fun findRecent(limit: Int): List<ActivityEvent>

    fun findRecentForOwner(ownerId: UUID, limit: Int): List<ActivityEvent> =
        findRecent(limit).filter { it.ownerId == ownerId || it.ownerId == null }.take(limit)

    fun findByCorrelation(ownerId: UUID, correlationId: UUID): List<ActivityEvent> =
        findRecentForOwner(ownerId, 1000).filter { it.ownerId == ownerId && it.correlationId == correlationId }.sortedBy { it.occurredAt }
}
