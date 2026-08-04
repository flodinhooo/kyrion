package dev.kyrion.core.memory

import java.time.Instant
import java.util.UUID

interface PersonalMemoryRepository {
    fun settings(ownerId: UUID): MemorySettings
    fun updateSettings(ownerId: UUID, enabled: Boolean, updatedAt: Instant): MemorySettings
    fun recent(ownerId: UUID, limit: Int): List<PersonalMemory>
    fun confirmed(ownerId: UUID, limit: Int): List<PersonalMemory>
    fun create(ownerId: UUID, memory: PersonalMemory): PersonalMemory
    fun find(ownerId: UUID, id: UUID): PersonalMemory?
    fun confirm(ownerId: UUID, id: UUID, confirmedAt: Instant, replaceConflict: Boolean): PersonalMemory?
    fun update(
        ownerId: UUID,
        id: UUID,
        category: MemoryCategory,
        content: String,
        sensitivity: MemorySensitivity,
        updatedAt: Instant,
    ): PersonalMemory?
    fun delete(ownerId: UUID, id: UUID): Boolean
}
