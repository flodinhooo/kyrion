package dev.kyrion.core.action

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityEvent
import dev.kyrion.core.activity.ActivityEventRepository
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.capability.DeviceCommandArguments
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.Locale
import java.util.UUID

class ActionOrchestratorTest {
    @Test
    fun `routine action executes once and retains authoritative correlation`() {
        val events = mutableListOf<ActivityEvent>()
        val handler = FakeActionHandler(ActionPolicyClass.ROUTINE)
        val orchestrator = orchestrator(handler, events)
        val context = context()

        val outcome = orchestrator.execute(context, proposal())

        assertEquals(ActionOutcomeStatus.SUCCEEDED, outcome.status)
        assertEquals("action.succeeded", outcome.code)
        assertEquals(context.correlationId, outcome.correlationId)
        assertEquals(1, handler.executions)
        assertEquals(listOf(ActivityStatus.PROPOSED, ActivityStatus.SUCCEEDED), events.map { it.status })
        assertTrue(events.all { it.correlationId == context.correlationId })
        assertTrue(events.none { it.summaryCode.contains("secret", ignoreCase = true) })
    }

    @Test
    fun `forbidden action is denied without domain execution`() {
        val events = mutableListOf<ActivityEvent>()
        val handler = FakeActionHandler(ActionPolicyClass.FORBIDDEN)
        val context = context(channel = InteractionChannel.VOICE)

        val outcome = orchestrator(handler, events).execute(context, proposal())

        assertEquals(ActionOutcomeStatus.REJECTED, outcome.status)
        assertEquals("action.denied", outcome.code)
        assertEquals(0, handler.executions)
        assertEquals(ActivityStatus.DENIED, events.last().status)
    }

    @Test
    fun `confirmation policy does not execute before confirmation`() {
        val events = mutableListOf<ActivityEvent>()
        val handler = FakeActionHandler(ActionPolicyClass.CONFIRMATION_REQUIRED)

        val outcome = orchestrator(handler, events).execute(context(), proposal())

        assertEquals(ActionOutcomeStatus.CONFIRMATION_REQUIRED, outcome.status)
        assertEquals(0, handler.executions)
        assertEquals(ActivityStatus.CONFIRMED, events.last().status)
    }

    @Test
    fun `voice session scope is rejected on a non voice channel`() {
        assertThrows(IllegalArgumentException::class.java) {
            context(channel = InteractionChannel.WEB, sessionId = UUID.randomUUID())
        }
    }

    private fun orchestrator(handler: FakeActionHandler, events: MutableList<ActivityEvent>) = ActionOrchestrator(
        listOf(handler),
        ActionPolicyService(),
        ActivityService(FakeActionActivityRepository(events), Clock.fixed(Instant.EPOCH, ZoneOffset.UTC)),
    )

    private fun context(
        channel: InteractionChannel = InteractionChannel.WEB,
        sessionId: UUID? = null,
    ) = ActionContext(
        ownerId = UUID.randomUUID(),
        actorType = ActivityActorType.USER,
        actorId = "owner",
        channel = channel,
        locale = Locale.GERMAN,
        correlationId = UUID.randomUUID(),
        idempotencyKey = UUID.randomUUID(),
        sessionId = sessionId,
    )

    private fun proposal() = DeviceActionProposal(
        UUID.randomUUID(),
        "power.set",
        DeviceCommandArguments(on = true),
    )
}

private class FakeActionHandler(
    private val classification: ActionPolicyClass,
) : ActionHandler<DeviceActionProposal> {
    var executions = 0
        private set

    override fun supports(proposal: ActionProposal) = proposal is DeviceActionProposal
    override fun policyClass(proposal: DeviceActionProposal) = classification
    override fun execute(context: ActionContext, proposal: DeviceActionProposal): ActionOutcome {
        executions += 1
        return ActionOutcome(
            ActionOutcomeStatus.SUCCEEDED,
            "action.succeeded",
            context.correlationId,
            proposal.capability,
            requested = 1,
            succeeded = 1,
        )
    }
}

private class FakeActionActivityRepository(
    private val events: MutableList<ActivityEvent>,
) : ActivityEventRepository {
    override fun append(event: ActivityEvent) = event.also(events::add)
    override fun findRecent(limit: Int) = events.takeLast(limit).reversed()
}
