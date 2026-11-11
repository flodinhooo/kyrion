package dev.kyrion.core.integration

import dev.kyrion.core.capability.DeviceAvailability
import dev.kyrion.core.capability.DeviceCapabilityUnsupportedException
import dev.kyrion.core.capability.DeviceTargetNotFoundException
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Service
import org.springframework.transaction.support.TransactionTemplate
import java.util.UUID

/** Called only through Core's common authority/capability/action boundary. */
@Service
class HomeAssistantCommandAdapter(
    private val connections: IntegrationConnectionRepository,
    private val selections: HomeAssistantSelectionStore,
    private val resolver: HomeAssistantConnectionResolver,
    private val client: HomeAssistantClient,
    private val readings: ImportedDeviceRepository,
    private val jdbc: JdbcClient,
    private val transactions: TransactionTemplate,
) {
    fun power(ownerId: UUID, connectionId: UUID, on: Boolean) {
        var confirmed = false
        try {
            transactions.executeWithoutResult {
                // Serialize consent/configuration changes with dispatch. Provider
                // requests have explicit connect/header/body timeouts.
                jdbc.sql("SELECT id FROM user_account WHERE id=:owner FOR UPDATE").param("owner", ownerId).query(UUID::class.java).single()
                val target = connections.find(ownerId, connectionId)?.takeIf {
                    it.provider == HOME_ASSISTANT_PROVIDER && it.credentialCiphertext.isEmpty()
                } ?: throw DeviceTargetNotFoundException()
                val selection = selections.load(ownerId) ?: throw DeviceCapabilityUnsupportedException()
                val choice = selection.devices.singleOrNull { it.externalId == target.endpointHost && it.control }
                    ?: throw DeviceCapabilityUnsupportedException()
                val config = resolver.resolve(ownerId) ?: throw HomeAssistantException("configuration_missing")
                val current = client.snapshot(config, mapOf(choice.externalId to choice.entities)).singleOrNull()
                    ?: throw HomeAssistantException("entity_unavailable")
                if (current.availability != DeviceAvailability.ONLINE) throw HomeAssistantException("entity_unavailable")
                val entity = current.entities.singleOrNull { it.supportsPower } ?: throw DeviceCapabilityUnsupportedException()
                val result = client.power(config, entity.id, on)
                confirmed = true
                val previous = readings.all(ownerId).singleOrNull { it.connectionId == connectionId }
                if (previous != null) {
                    // Keep the oldest source timestamp for a multi-entity device;
                    // updating power does not make unrelated sensor values fresh.
                    val measured = previous.state.measuredAt?.let { old -> result.updatedAt?.let { minOf(old, it) } ?: old }
                    readings.save(ownerId, previous.copy(state = previous.state.copy(on = result.on, measuredAt = measured)))
                }
            }
        } catch (failure: RuntimeException) {
            // A database persistence failure after a verified provider effect
            // must not transform that confirmed physical action into a retry.
            if (!confirmed) throw failure
        }
    }
}
