package dev.kyrion.core.integration

import java.util.UUID

interface IntegrationConnectionRepository {
    fun findAll(ownerId: UUID): List<IntegrationConnection>
    fun find(ownerId: UUID, id: UUID): IntegrationConnection?
    fun save(connection: IntegrationConnection): IntegrationConnection
    fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: java.time.Instant): IntegrationConnection?
    fun delete(ownerId: UUID, id: UUID): Boolean
}
