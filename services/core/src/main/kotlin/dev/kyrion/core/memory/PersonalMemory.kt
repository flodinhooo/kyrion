package dev.kyrion.core.memory

import java.time.Instant
import java.util.UUID

enum class MemoryCategory { preference, person, project, value, other }
enum class MemorySensitivity { standard, sensitive }
enum class MemoryStatus { proposed, confirmed, superseded }

data class MemorySettings(
    val enabled: Boolean, val updatedAt: Instant?,
    val historyEnabled: Boolean = false, val preferencesEnabled: Boolean = false,
    val categories: List<MemoryCategory> = MemoryCategory.entries.toList()
)

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
    val conflictsWithMemoryId: UUID? = null,
    val active: Boolean = true,
    val expiresAt: Instant? = null,
    val ownerId: UUID? = null,
)

data class MemoryProfile(val settings: MemorySettings, val items: List<PersonalMemory>)
