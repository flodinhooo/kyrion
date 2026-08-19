package dev.kyrion.core.action

import com.fasterxml.jackson.annotation.JsonSubTypes
import com.fasterxml.jackson.annotation.JsonTypeInfo
import com.fasterxml.jackson.annotation.JsonValue
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.capability.DeviceCommandArguments
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Size
import java.util.Locale
import java.util.UUID

enum class InteractionChannel(@get:JsonValue val value: String) {
    WEB("web"),
    VOICE("voice"),
    MOBILE("mobile"),
    AUTOMATION("automation"),
    INTEGRATION("integration"),
}

enum class ActionPolicyClass(@get:JsonValue val value: String) {
    READ("read"),
    ROUTINE("routine"),
    CONFIRMATION_REQUIRED("confirmation_required"),
    RESTRICTED("restricted"),
    FORBIDDEN("forbidden"),
}

enum class ActionDecisionType(@get:JsonValue val value: String) {
    ALLOWED("allowed"),
    CONFIRMATION_REQUIRED("confirmation_required"),
    REJECTED("rejected"),
}

enum class ActionOutcomeStatus(@get:JsonValue val value: String) {
    SUCCEEDED("succeeded"),
    PARTIALLY_SUCCEEDED("partially_succeeded"),
    FAILED("failed"),
    REJECTED("rejected"),
    CONFIRMATION_REQUIRED("confirmation_required"),
}

data class ActionContext(
    val ownerId: UUID,
    val actorType: ActivityActorType,
    val actorId: String?,
    val channel: InteractionChannel,
    val locale: Locale,
    val correlationId: UUID,
    val idempotencyKey: UUID,
    val sessionId: UUID? = null,
    val conversationId: UUID? = null,
) {
    init {
        require(locale.language in SUPPORTED_LANGUAGES) { "Unsupported action locale" }
        require(sessionId == null || channel == InteractionChannel.VOICE) {
            "A voice session is only valid for the voice channel"
        }
    }

    companion object {
        private val SUPPORTED_LANGUAGES = setOf("de", "en")
    }
}

@JsonTypeInfo(use = JsonTypeInfo.Id.NAME, include = JsonTypeInfo.As.PROPERTY, property = "type")
@JsonSubTypes(JsonSubTypes.Type(value = DeviceActionProposal::class, name = "device"))
sealed interface ActionProposal

data class DeviceActionProposal(
    val targetId: UUID,
    @field:NotBlank @field:Size(max = 80) val capability: String,
    @field:Valid val arguments: DeviceCommandArguments,
) : ActionProposal

data class ActionDecision(
    val type: ActionDecisionType,
    val policyClass: ActionPolicyClass,
    val code: String,
)

data class ActionTargetOutcome(
    val targetId: UUID,
    val displayName: String,
    val status: String,
)

data class ActionOutcome(
    val status: ActionOutcomeStatus,
    val code: String,
    val correlationId: UUID,
    val capability: String? = null,
    val requested: Int = 0,
    val succeeded: Int = 0,
    val failed: Int = 0,
    val targets: List<ActionTargetOutcome> = emptyList(),
)
