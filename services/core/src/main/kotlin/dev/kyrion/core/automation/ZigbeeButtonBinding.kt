package dev.kyrion.core.automation

import dev.kyrion.core.action.ActionContext
import dev.kyrion.core.action.ActionOrchestrator
import dev.kyrion.core.action.DeviceActionProposal
import dev.kyrion.core.action.InteractionChannel
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.capability.DeviceCatalogService
import dev.kyrion.core.capability.DeviceCommandArguments
import dev.kyrion.core.capability.DeviceCommandService
import dev.kyrion.core.gateway.GatewayNode
import dev.kyrion.core.integration.IntegrationConnectionRepository
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.Pattern
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController
import java.sql.Timestamp
import java.time.Clock
import java.util.Locale
import java.util.UUID

data class ZigbeeButtonBinding(
    val gesture: String,
    val targetDeviceId: UUID,
    val action: String,
)

data class ReplaceZigbeeButtonBindingsRequest(val bindings: List<@Valid ZigbeeButtonBinding>)

@Repository
class ZigbeeButtonBindingRepository(private val jdbc: JdbcClient) {
    fun find(ownerId: UUID, buttonId: UUID): List<ZigbeeButtonBinding> = jdbc.sql(
        """SELECT gesture, target_connection_id, action FROM zigbee_button_binding
           WHERE owner_id=:ownerId AND button_connection_id=:buttonId ORDER BY gesture""",
    ).param("ownerId", ownerId).param("buttonId", buttonId).query { rs, _ ->
        ZigbeeButtonBinding(rs.getString("gesture"), rs.getObject("target_connection_id", UUID::class.java), rs.getString("action"))
    }.list()

    @Transactional
    fun replace(ownerId: UUID, buttonId: UUID, bindings: List<ZigbeeButtonBinding>, now: java.time.Instant) {
        jdbc.sql("DELETE FROM zigbee_button_binding WHERE owner_id=:ownerId AND button_connection_id=:buttonId")
            .param("ownerId", ownerId).param("buttonId", buttonId).update()
        bindings.forEach { binding ->
            jdbc.sql(
                """INSERT INTO zigbee_button_binding
                   (owner_id, button_connection_id, gesture, target_connection_id, action, updated_at)
                   VALUES (:ownerId, :buttonId, :gesture, :targetId, :action, :updatedAt)""",
            ).param("ownerId", ownerId).param("buttonId", buttonId).param("gesture", binding.gesture)
                .param("targetId", binding.targetDeviceId).param("action", binding.action)
                .param("updatedAt", Timestamp.from(now)).update()
        }
    }
}

@Service
class ZigbeeButtonBindingService(
    private val repository: ZigbeeButtonBindingRepository,
    private val connections: IntegrationConnectionRepository,
    private val catalog: DeviceCatalogService,
    private val orchestrator: ActionOrchestrator,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun find(ownerId: UUID, buttonId: UUID): List<ZigbeeButtonBinding> {
        requireButton(ownerId, buttonId)
        return repository.find(ownerId, buttonId)
    }

    fun replace(ownerId: UUID, buttonId: UUID, bindings: List<ZigbeeButtonBinding>): List<ZigbeeButtonBinding> {
        requireButton(ownerId, buttonId)
        if (bindings.size > 3 || bindings.map { it.gesture }.distinct().size != bindings.size ||
            bindings.any { it.gesture !in GESTURES || it.action !in ACTIONS }) throw ZigbeeButtonBindingInvalidException()
        val targets = catalog.devices(ownerId).associateBy { it.id }
        if (bindings.any { binding ->
                val target = targets[binding.targetDeviceId]
                target == null || target.id == buttonId || target.capabilities.none { it.id == DeviceCommandService.POWER_SET }
            }) throw ZigbeeButtonBindingInvalidException()
        repository.replace(ownerId, buttonId, bindings, clock.instant())
        return repository.find(ownerId, buttonId)
    }

    fun handle(node: GatewayNode, ieeeAddress: String, gesture: String) {
        if (gesture !in GESTURES) throw ZigbeeButtonBindingInvalidException()
        val button = connections.findAll(node.ownerId).singleOrNull {
            it.provider == "zigbee" && it.endpointHost == ieeeAddress
        } ?: throw ZigbeeButtonBindingInvalidException()
        requireButton(node.ownerId, button.id)
        val binding = repository.find(node.ownerId, button.id).singleOrNull { it.gesture == gesture } ?: return
        val target = catalog.devices(node.ownerId).singleOrNull { it.id == binding.targetDeviceId }
            ?: throw ZigbeeButtonBindingInvalidException()
        val on = when (binding.action) {
            "turn_on" -> true
            "turn_off" -> false
            "toggle" -> !(target.state?.on ?: false)
            else -> throw ZigbeeButtonBindingInvalidException()
        }
        orchestrator.execute(
            ActionContext(node.ownerId, ActivityActorType.INTEGRATION, button.id.toString(), InteractionChannel.AUTOMATION,
                Locale.GERMAN, UUID.randomUUID(), UUID.randomUUID()),
            DeviceActionProposal(target.id, DeviceCommandService.POWER_SET, DeviceCommandArguments(on = on)),
        )
    }

    private fun requireButton(ownerId: UUID, buttonId: UUID) {
        val device = catalog.devices(ownerId).singleOrNull { it.id == buttonId }
        if (device?.provider != "zigbee" || device.capabilities.none { it.id == "button.events" }) {
            throw ZigbeeButtonBindingInvalidException()
        }
    }

    companion object {
        val GESTURES = setOf("single", "double", "long")
        val ACTIONS = setOf("toggle", "turn_on", "turn_off")
    }
}

@RestController
@RequestMapping("/v1/devices/{buttonId}/button-bindings")
class ZigbeeButtonBindingController(private val service: ZigbeeButtonBindingService) {
    @GetMapping fun find(@PathVariable buttonId: UUID, request: HttpServletRequest) = service.find(request.ownerId(), buttonId)

    @PutMapping fun replace(@PathVariable buttonId: UUID, @Valid @RequestBody body: ReplaceZigbeeButtonBindingsRequest,
        request: HttpServletRequest) = service.replace(request.ownerId(), buttonId, body.bindings)

    private fun HttpServletRequest.ownerId() = getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID
        ?: throw ZigbeeButtonBindingInvalidException()
}

class ZigbeeButtonBindingInvalidException : RuntimeException()
