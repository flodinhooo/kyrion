package dev.kyrion.core.action

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.capability.DeviceAvailability
import dev.kyrion.core.capability.DeviceCapabilityUnsupportedException
import dev.kyrion.core.capability.DeviceCatalogService
import dev.kyrion.core.capability.DeviceCommandService
import dev.kyrion.core.capability.DeviceTargetNotFoundException
import dev.kyrion.core.capability.DeviceTargetSelector
import dev.kyrion.core.capability.ExecuteDeviceCommandRequest
import org.springframework.stereotype.Service

interface ActionHandler<P : ActionProposal> {
    fun supports(proposal: ActionProposal): Boolean
    fun policyClass(proposal: P): ActionPolicyClass
    fun execute(context: ActionContext, proposal: P): ActionOutcome
}

@Service
class ActionPolicyService {
    fun decide(context: ActionContext, policyClass: ActionPolicyClass): ActionDecision = when (policyClass) {
        ActionPolicyClass.READ, ActionPolicyClass.ROUTINE -> ActionDecision(
            ActionDecisionType.ALLOWED,
            policyClass,
            "action.allowed",
        )
        ActionPolicyClass.CONFIRMATION_REQUIRED -> ActionDecision(
            ActionDecisionType.CONFIRMATION_REQUIRED,
            policyClass,
            "action.confirmation_required",
        )
        ActionPolicyClass.RESTRICTED, ActionPolicyClass.FORBIDDEN -> ActionDecision(
            ActionDecisionType.REJECTED,
            policyClass,
            "action.denied",
        )
    }
}

@Service
class ActionOrchestrator(
    handlers: List<ActionHandler<out ActionProposal>>,
    private val policy: ActionPolicyService,
    private val activity: ActivityService,
) {
    private val handlers = handlers.toList()

    fun execute(context: ActionContext, proposal: ActionProposal): ActionOutcome {
        record(context, "action.proposed", ActivityStatus.PROPOSED, "action.proposed")
        val handler = handlers.singleOrNull { it.supports(proposal) } ?: return rejected(
            context,
            "action.unsupported",
        )
        return executeTyped(context, proposal, handler)
    }

    @Suppress("UNCHECKED_CAST")
    private fun executeTyped(
        context: ActionContext,
        proposal: ActionProposal,
        handler: ActionHandler<out ActionProposal>,
    ): ActionOutcome {
        val typedHandler = handler as ActionHandler<ActionProposal>
        val decision = policy.decide(context, typedHandler.policyClass(proposal))
        when (decision.type) {
            ActionDecisionType.REJECTED -> return rejected(context, decision.code)
            ActionDecisionType.CONFIRMATION_REQUIRED -> {
                record(context, "action.confirmation_required", ActivityStatus.CONFIRMED, decision.code)
                return ActionOutcome(
                    ActionOutcomeStatus.CONFIRMATION_REQUIRED,
                    decision.code,
                    context.correlationId,
                )
            }
            ActionDecisionType.ALLOWED -> Unit
        }

        val outcome = try {
            typedHandler.execute(context, proposal)
        } catch (_: DeviceTargetNotFoundException) {
            ActionOutcome(ActionOutcomeStatus.REJECTED, "target.not_found", context.correlationId)
        } catch (_: DeviceCapabilityUnsupportedException) {
            ActionOutcome(ActionOutcomeStatus.REJECTED, "action.unsupported", context.correlationId)
        } catch (_: IllegalArgumentException) {
            ActionOutcome(ActionOutcomeStatus.REJECTED, "proposal.invalid", context.correlationId)
        }
        val eventStatus = when (outcome.status) {
            ActionOutcomeStatus.SUCCEEDED -> ActivityStatus.SUCCEEDED
            ActionOutcomeStatus.PARTIALLY_SUCCEEDED, ActionOutcomeStatus.FAILED -> ActivityStatus.FAILED
            ActionOutcomeStatus.REJECTED -> ActivityStatus.DENIED
            ActionOutcomeStatus.CONFIRMATION_REQUIRED -> ActivityStatus.CONFIRMED
        }
        record(context, "action.completed", eventStatus, outcome.code)
        return outcome
    }

    private fun rejected(context: ActionContext, code: String): ActionOutcome {
        record(context, "action.rejected", ActivityStatus.DENIED, code)
        return ActionOutcome(ActionOutcomeStatus.REJECTED, code, context.correlationId)
    }

    private fun record(context: ActionContext, type: String, status: ActivityStatus, code: String) {
        activity.record(
            ActivityCategory.CAPABILITY,
            type,
            status,
            context.actorType,
            "kyrion-core",
            code,
            context.actorId,
            context.correlationId,
            context.ownerId,
        )
    }
}

@Service
class DeviceActionHandler(
    private val catalog: DeviceCatalogService,
    private val commands: DeviceCommandService,
) : ActionHandler<DeviceActionProposal> {
    override fun supports(proposal: ActionProposal) = proposal is DeviceActionProposal

    override fun policyClass(proposal: DeviceActionProposal) = when (proposal.capability) {
        DeviceCommandService.POWER_SET,
        DeviceCommandService.BRIGHTNESS_SET,
        DeviceCommandService.COLOR_SET,
        -> ActionPolicyClass.ROUTINE
        else -> ActionPolicyClass.FORBIDDEN
    }

    override fun execute(context: ActionContext, proposal: DeviceActionProposal): ActionOutcome {
        val requestedIds = (proposal.targetIds + listOfNotNull(proposal.targetId)).distinct()
        val targets = catalog.devices(context.ownerId).filter { it.id in requestedIds }
        if (targets.size != requestedIds.size) throw DeviceTargetNotFoundException()
        if (targets.any { target -> target.capabilities.none { it.id == proposal.capability } }) {
            throw DeviceCapabilityUnsupportedException()
        }
        val results = targets.map { target ->
            commands.execute(
                context.ownerId,
                ExecuteDeviceCommandRequest(
                    proposal.capability,
                    DeviceTargetSelector(provider = target.provider, deviceId = target.id),
                    proposal.arguments,
                ),
                context.correlationId,
                recordProposal = false,
            )
        }
        val outcomes = results.flatMap { it.outcomes }
        val requested = outcomes.size
        val succeeded = outcomes.count { it.status == "succeeded" }
        val failed = requested - succeeded
        val unavailable = outcomes.isNotEmpty() && outcomes.all { it.status == "unavailable" }
        val status = when {
            succeeded == requested -> ActionOutcomeStatus.SUCCEEDED
            succeeded > 0 -> ActionOutcomeStatus.PARTIALLY_SUCCEEDED
            else -> ActionOutcomeStatus.FAILED
        }
        val code = when {
            unavailable -> "device.offline"
            status == ActionOutcomeStatus.SUCCEEDED -> "action.succeeded"
            status == ActionOutcomeStatus.PARTIALLY_SUCCEEDED -> "action.partially_succeeded"
            else -> "action.failed"
        }
        return ActionOutcome(
            status,
            code,
            context.correlationId,
            proposal.capability,
            requested,
            succeeded,
            failed,
            outcomes.map { ActionTargetOutcome(it.deviceId, it.displayName, it.status) },
        )
    }
}
