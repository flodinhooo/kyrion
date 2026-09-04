package dev.kyrion.core.integration

import java.util.UUID

interface IntegrationConnectionRepository {
    fun findAll(ownerId: UUID): List<IntegrationConnection>
    fun find(ownerId: UUID, id: UUID): IntegrationConnection?
    fun save(connection: IntegrationConnection): IntegrationConnection
    fun rename(ownerId: UUID, id: UUID, displayName: String, updatedAt: java.time.Instant): IntegrationConnection?
    fun update(ownerId: UUID, id: UUID, displayName: String, deviceClass: DeviceClass, updatedAt: java.time.Instant): IntegrationConnection? =
        rename(ownerId, id, displayName, updatedAt)
    fun updateCredential(ownerId: UUID, id: UUID, credential: ProtectedCredential, updatedAt: java.time.Instant): IntegrationConnection? = null
    fun delete(ownerId: UUID, id: UUID): Boolean
}
