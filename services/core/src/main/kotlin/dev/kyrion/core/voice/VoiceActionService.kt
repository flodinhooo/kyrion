package dev.kyrion.core.voice

import dev.kyrion.core.action.ActionContext
import dev.kyrion.core.action.ActionExecutionService
import dev.kyrion.core.action.ActionOutcomeStatus
import dev.kyrion.core.action.ActionPriorMessage
import dev.kyrion.core.action.ActionResultRenderer
import dev.kyrion.core.action.DeviceProposalProvider
import dev.kyrion.core.action.DeviceActionProposal
import dev.kyrion.core.action.InteractionChannel
import dev.kyrion.core.action.ProposalResult
import dev.kyrion.core.activity.ActivityActorType
import org.springframework.stereotype.Service
import java.util.Locale
import java.util.UUID

sealed interface VoiceActionAttempt {
    data object NotAction : VoiceActionAttempt
    data class Respond(val outcome: DialogueOutcome) : VoiceActionAttempt
    data class Pending(val context: ActionContext, val proposal: DeviceActionProposal) : VoiceActionAttempt
}

@Service
class VoiceActionService(
    private val proposals: DeviceProposalProvider,
    private val executions: ActionExecutionService,
    private val renderer: ActionResultRenderer,
) {
    fun interpret(
        ownerId: UUID,
        satelliteId: UUID,
        sessionId: UUID,
        conversationId: UUID,
        turnId: UUID,
        locale: String,
        message: String,
        priorMessages: List<ActionPriorMessage>,
        validateActive: () -> Unit = {},
        onValidated: () -> Unit = {},
        deferExecution: Boolean = false,
    ): VoiceActionAttempt = when (val result = proposals.propose(ownerId, message.trim(), locale, priorMessages)) {
        is ProposalResult.Proposed -> {
            validateActive()
            onValidated()
            validateActive()
            val context = ActionContext(
                ownerId = ownerId,
                actorType = ActivityActorType.INTEGRATION,
                actorId = satelliteId.toString(),
                channel = InteractionChannel.VOICE,
                locale = Locale.forLanguageTag(locale),
                correlationId = turnId,
                idempotencyKey = turnId,
                sessionId = sessionId,
                conversationId = conversationId,
            )
            if (deferExecution) VoiceActionAttempt.Pending(context, result.proposal)
            else execute(context, result.proposal)
        }
        ProposalResult.None -> VoiceActionAttempt.NotAction
        ProposalResult.Ambiguous -> VoiceActionAttempt.Respond(
            DynamicDialogueOutcome(renderer.rejection("target.ambiguous", locale)),
        )
        ProposalResult.Invalid -> VoiceActionAttempt.Respond(
            DynamicDialogueOutcome(renderer.rejection("proposal.invalid", locale)),
        )
        ProposalResult.Unavailable -> VoiceActionAttempt.Respond(DynamicDialogueOutcome(
            if (locale == "de") "Ich konnte die Aktion gerade nicht sicher prüfen."
            else "I couldn't safely evaluate that action right now.",
        ))
    }

    fun execute(context: ActionContext, proposal: DeviceActionProposal): VoiceActionAttempt.Respond {
        val outcome = executions.execute(context, proposal)
        val targetName = outcome.targets.joinToString(", ") { it.displayName }.takeIf { it.isNotBlank() }
        val response = if (targetName != null) {
            CommandExecutionOutcome(
                executionConfirmed = true,
                succeeded = outcome.status == ActionOutcomeStatus.SUCCEEDED,
                targetName = targetName,
            )
        } else {
            DynamicDialogueOutcome(renderer.rejection(outcome.code, context.locale.language))
        }
        return VoiceActionAttempt.Respond(response)
    }
}
