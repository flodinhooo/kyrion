package dev.kyrion.core.voice

import dev.kyrion.core.action.*
import dev.kyrion.core.activity.*
import dev.kyrion.core.capability.DeviceCommandArguments
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.Instant
import java.util.UUID

class VoiceActionServiceTest {
    @Test
    fun `proposed action executes once with correlated voice context`() {
        val proposal = DeviceActionProposal(UUID.randomUUID(), "power.set", DeviceCommandArguments(on = true))
        val handler = CapturingVoiceHandler()
        val service = service(ProposalResult.Proposed(proposal), handler)
        val turnId = UUID.randomUUID()
        val sessionId = UUID.randomUUID()

        val result = service.interpret(
            UUID.randomUUID(), UUID.randomUUID(), sessionId, UUID.randomUUID(), turnId,
            "de", "Mach das Licht an", emptyList(),
        )

        assertTrue(result is VoiceActionAttempt.Respond)
        assertEquals(1, handler.executions)
        assertEquals(InteractionChannel.VOICE, handler.context?.channel)
        assertEquals(turnId, handler.context?.correlationId)
        assertEquals(turnId, handler.context?.idempotencyKey)
        assertEquals(sessionId, handler.context?.sessionId)
        assertEquals(true, ((result as VoiceActionAttempt.Respond).outcome as CommandExecutionOutcome).succeeded)
    }

    @Test
    fun `ordinary dialogue does not execute an action`() {
        val handler = CapturingVoiceHandler()

        val result = service(ProposalResult.None, handler).interpret(
            UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
            "de", "Wie geht es dir", emptyList(),
        )

        assertSame(VoiceActionAttempt.NotAction, result)
        assertEquals(0, handler.executions)
    }

    @Test
    fun `validated processing callback runs before device execution`() {
        val order = mutableListOf<String>()
        val proposal = DeviceActionProposal(UUID.randomUUID(), "power.set", DeviceCommandArguments(on = true))
        val handler = CapturingVoiceHandler { order += "execute" }

        service(ProposalResult.Proposed(proposal), handler).interpret(
            UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
            "de", "Mach das Licht an", emptyList(),
            onValidated = { order += "processing" },
        )

        assertEquals(listOf("processing", "execute"), order)
    }

    @Test
    fun `ambiguous target is rejected without execution`() {
        val handler = CapturingVoiceHandler()

        val result = service(ProposalResult.Ambiguous, handler).interpret(
            UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
            "de", "Mach im Büro das Licht an", emptyList(),
        ) as VoiceActionAttempt.Respond

        assertEquals("Das Ziel ist nicht eindeutig.", (result.outcome as DynamicDialogueOutcome).text)
        assertEquals(0, handler.executions)
    }

    @Test
    fun `inactive session check prevents execution after proposal`() {
        val proposal = DeviceActionProposal(UUID.randomUUID(), "power.set", DeviceCommandArguments(on = true))
        val handler = CapturingVoiceHandler()

        assertThrows(VoiceSessionInactiveException::class.java) {
            service(ProposalResult.Proposed(proposal), handler).interpret(
                UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(), UUID.randomUUID(),
                "de", "Mach das Licht an", emptyList(),
            ) { throw VoiceSessionInactiveException() }
        }
        assertEquals(0, handler.executions)
    }

    private fun service(result: ProposalResult, handler: CapturingVoiceHandler): VoiceActionService {
        val executions = ActionExecutionService(
            MemoryVoiceExecutions(),
            ActionOrchestrator(listOf(handler), ActionPolicyService(), ActivityService(EmptyVoiceActivityRepository())),
            Clock.fixed(Instant.EPOCH, java.time.ZoneOffset.UTC),
        )
        return VoiceActionService(FixedProposalProvider(result), executions, ActionResultRenderer())
    }
}

private class FixedProposalProvider(private val result: ProposalResult) : DeviceProposalProvider {
    override fun propose(ownerId: UUID, message: String, locale: String, priorMessages: List<ActionPriorMessage>) = result
}

private class CapturingVoiceHandler(private val beforeExecute: () -> Unit = {}) : ActionHandler<DeviceActionProposal> {
    var executions = 0
    var context: ActionContext? = null
    override fun supports(proposal: ActionProposal) = proposal is DeviceActionProposal
    override fun policyClass(proposal: DeviceActionProposal) = ActionPolicyClass.ROUTINE
    override fun execute(context: ActionContext, proposal: DeviceActionProposal): ActionOutcome {
        beforeExecute()
        executions += 1
        this.context = context
        return ActionOutcome(
            ActionOutcomeStatus.SUCCEEDED, "action.succeeded", context.correlationId, proposal.capability,
            1, 1, 0, listOf(ActionTargetOutcome(requireNotNull(proposal.targetId), "Bürolicht", "succeeded")),
        )
    }
}

private class MemoryVoiceExecutions : ActionExecutionRepository {
    private val values = mutableMapOf<Pair<UUID, UUID>, ActionExecutionRecord>()
    override fun claim(ownerId: UUID, idempotencyKey: UUID, correlationId: UUID, requestHash: String, now: Instant): Boolean {
        val key = ownerId to idempotencyKey
        if (values.containsKey(key)) return false
        values[key] = ActionExecutionRecord(correlationId, requestHash, "pending", null)
        return true
    }
    override fun find(ownerId: UUID, idempotencyKey: UUID) = values[ownerId to idempotencyKey]
    override fun complete(ownerId: UUID, idempotencyKey: UUID, outcomeJson: String, now: Instant): Boolean {
        val key = ownerId to idempotencyKey
        val current = values[key] ?: return false
        values[key] = current.copy(status = "completed", outcomeJson = outcomeJson)
        return true
    }
}

private class EmptyVoiceActivityRepository : ActivityEventRepository {
    override fun append(event: ActivityEvent) = event
    override fun findRecent(limit: Int) = emptyList<ActivityEvent>()
}
