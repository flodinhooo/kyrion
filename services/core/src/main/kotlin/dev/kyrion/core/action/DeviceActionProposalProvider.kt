package dev.kyrion.core.action

import dev.kyrion.core.capability.DeviceCatalogService
import dev.kyrion.core.capability.DeviceCommandArguments
import dev.kyrion.core.home.RoomResolution
import dev.kyrion.core.home.RoomResolver
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.MediaType
import org.springframework.stereotype.Service
import org.springframework.web.client.RestClient
import java.util.UUID

data class ActionPriorMessage(val role: String, val content: String)
data class DeviceProposalIntentRequest(
    val message: String,
    val locale: String,
    val priorMessages: List<ActionPriorMessage>,
    val devices: List<SafeDeviceProposalView>,
)
data class SafeDeviceProposalView(
    val id: UUID,
    val provider: String,
    val displayName: String,
    val roomName: String?,
    val capabilities: List<Map<String, String>>,
    val availability: String,
    val observedAt: String?,
)
data class AiDeviceSelector(val provider: String, val roomName: String? = null, val deviceId: String? = null)
data class AiDeviceArguments(val on: Boolean? = null, val brightness: Int? = null)
data class AiDeviceProposal(val capability: String, val selector: AiDeviceSelector, val arguments: AiDeviceArguments)
data class AiDeviceProposalResponse(val proposal: AiDeviceProposal? = null)

sealed interface ProposalResult {
    data class Proposed(val proposal: DeviceActionProposal) : ProposalResult
    data object None : ProposalResult
    data object Ambiguous : ProposalResult
    data object Invalid : ProposalResult
    data object Unavailable : ProposalResult
}

interface DeviceProposalProvider {
    fun propose(ownerId: UUID, message: String, locale: String, priorMessages: List<ActionPriorMessage>): ProposalResult
}

@Service
class CoreDeviceProposalProvider(
    private val catalog: DeviceCatalogService,
    private val rooms: RoomResolver,
    @Value("\${kyrion.ai.base-url:http://127.0.0.1:8000}") aiBaseUrl: String,
) : DeviceProposalProvider {
    private val client = RestClient.builder().baseUrl(aiBaseUrl).build()

    override fun propose(ownerId: UUID, message: String, locale: String, priorMessages: List<ActionPriorMessage>): ProposalResult {
        val devices = catalog.devices(ownerId)
        val response = try {
            client.post().uri("/v1/device-commands/propose").contentType(MediaType.APPLICATION_JSON)
                .body(DeviceProposalIntentRequest(message, locale, priorMessages, devices.map {
                    SafeDeviceProposalView(it.id, it.provider, it.displayName, it.room?.name,
                        it.capabilities.map { capability -> mapOf("id" to capability.id) }, it.availability.value,
                        it.observedAt?.toString())
                })).retrieve().body(AiDeviceProposalResponse::class.java)
        } catch (_: RuntimeException) { return ProposalResult.Unavailable }
        val proposed = response?.proposal ?: return ProposalResult.None
        if (proposed.selector.provider != "nanoleaf") return ProposalResult.Invalid
        val candidates = when {
            proposed.selector.deviceId != null -> {
                val id = runCatching { UUID.fromString(proposed.selector.deviceId) }.getOrNull()
                    ?: return ProposalResult.Invalid
                devices.filter { it.id == id }
            }
            proposed.selector.roomName != null -> when (val resolution = rooms.resolve(ownerId, proposed.selector.roomName, locale)) {
                is RoomResolution.Resolved -> devices.filter { it.room?.id == resolution.room.id }
                RoomResolution.Ambiguous -> return ProposalResult.Ambiguous
                RoomResolution.NotFound -> return ProposalResult.Invalid
            }
            else -> return ProposalResult.Invalid
        }.filter { device -> device.provider == proposed.selector.provider && device.capabilities.any { it.id == proposed.capability } }
        if (candidates.size > 1) return ProposalResult.Ambiguous
        val target = candidates.singleOrNull() ?: return ProposalResult.Invalid
        val arguments = when (proposed.capability) {
            "power.set" -> proposed.arguments.on?.let { DeviceCommandArguments(on = it) }
            "light.setBrightness" -> proposed.arguments.brightness?.takeIf { it in 0..100 }
                ?.let { DeviceCommandArguments(brightness = it) }
            else -> null
        } ?: return ProposalResult.Invalid
        return ProposalResult.Proposed(DeviceActionProposal(target.id, proposed.capability, arguments))
    }
}
