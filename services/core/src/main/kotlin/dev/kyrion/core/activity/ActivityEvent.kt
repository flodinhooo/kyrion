package dev.kyrion.core.activity

import com.fasterxml.jackson.annotation.JsonIgnore
import java.time.Instant
import java.util.UUID

data class ActivityEvent(
    val id: UUID,
    val occurredAt: Instant,
    val category: ActivityCategory,
    val eventType: String,
    val status: ActivityStatus,
    val actorType: ActivityActorType,
    val actorId: String?,
    val source: String,
    val correlationId: UUID,
    val summaryCode: String,
    @get:JsonIgnore val ownerId: UUID? = null,
)

enum class ActivityCategory {
    SYSTEM,
    CAPABILITY,
    INTEGRATION,
    AUTOMATION,
    SECURITY,
}

enum class ActivityStatus {
    PROPOSED,
    CONFIRMED,
    SUCCEEDED,
    FAILED,
    DENIED,
}

enum class ActivityActorType {
    SYSTEM,
    USER,
    AI,
    INTEGRATION,
}
