package dev.kyrion.core.memory

import java.time.Instant
import java.util.UUID

enum class MemoryCategory { preference, person, project, value, other }
enum class MemorySensitivity { standard, sensitive }
enum class MemoryStatus { proposed, confirmed }

data class MemorySettings(val enabled: Boolean, val updatedAt: Instant?)

data class PersonalMemory(
    val id: UUID,
    val category: MemoryCategory,
    val content: String,
    val sensitivity: MemorySensitivity,
    val origin: String,
    val status: MemoryStatus,
    val sourceConversationId: UUID?,
    val sourceMessageId: UUID?,
    val createdAt: Instant,
    val updatedAt: Instant,
    val confirmedAt: Instant?,
)

data class MemoryProfile(val settings: MemorySettings, val items: List<PersonalMemory>)
