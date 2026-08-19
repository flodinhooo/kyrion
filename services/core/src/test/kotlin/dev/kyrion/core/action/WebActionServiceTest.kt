package dev.kyrion.core.action

import dev.kyrion.core.activity.ActivityEvent
import dev.kyrion.core.activity.ActivityEventRepository
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.capability.DeviceCommandArguments
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNotEquals
import org.junit.jupiter.api.Assertions.assertThrows
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

class WebActionServiceTest {
    @Test
    fun `completed request replays stored outcome without executing twice`() {
        val repository = InMemoryActionExecutions()
        val handler = CountingWebActionHandler()
        val service = service(repository, handler)
        val owner = UUID.randomUUID()
        val request = request()

        val first = service.execute(owner, request)
        val replay = service.execute(owner, request)

        assertEquals(first, replay)
        assertEquals(1, handler.executions)
    }

    @Test
    fun `same key with changed proposal is rejected`() {
        val repository = InMemoryActionExecutions()
        val handler = CountingWebActionHandler()
        val service = service(repository, handler)
        val owner = UUID.randomUUID()
        val first = request()
        service.execute(owner, first)

        assertThrows(ActionIdempotencyMismatchException::class.java) {
            service.execute(owner, first.copy(proposal = proposal(on = false)))
        }
        assertEquals(1, handler.executions)
    }

    @Test
    fun `pending request cannot start a second execution`() {
        val repository = InMemoryActionExecutions()
        val handler = CountingWebActionHandler()
        val service = service(repository, handler)
        val owner = UUID.randomUUID()
        val request = request()
        val hashService = service(repository, handler)
        // A repository claim without completion models an in-flight transaction.
        assertThrows(ActionExecutionPendingException::class.java) {
            repository.forcePending(owner, request)
            hashService.execute(owner, request)
        }
        assertEquals(0, handler.executions)
    }

    @Test
    fun `idempotency keys are isolated per owner`() {
        val repository = InMemoryActionExecutions()
        val handler = CountingWebActionHandler()
        val service = service(repository, handler)
        val request = request()

        val first = service.execute(UUID.randomUUID(), request)
        val second = service.execute(UUID.randomUUID(), request)

        assertEquals(2, handler.executions)
        assertNotEquals(first.correlationId, second.correlationId)
    }

    private fun service(repository: InMemoryActionExecutions, handler: CountingWebActionHandler): WebActionService {
        val activity = ActivityService(EmptyWebActionActivityRepository(), Clock.fixed(Instant.EPOCH, ZoneOffset.UTC))
        return WebActionService(repository, ActionOrchestrator(listOf(handler), ActionPolicyService(), activity), Clock.fixed(Instant.EPOCH, ZoneOffset.UTC))
    }

    private fun request() = WebActionRequest(UUID.randomUUID(), "de", proposal())
    private fun proposal(on: Boolean = true) = DeviceActionProposal(UUID.randomUUID(), "power.set", DeviceCommandArguments(on = on))
}

private class CountingWebActionHandler : ActionHandler<DeviceActionProposal> {
    var executions = 0
    override fun supports(proposal: ActionProposal) = proposal is DeviceActionProposal
    override fun policyClass(proposal: DeviceActionProposal) = ActionPolicyClass.ROUTINE
    override fun execute(context: ActionContext, proposal: DeviceActionProposal): ActionOutcome {
        executions += 1
        return ActionOutcome(ActionOutcomeStatus.SUCCEEDED, "action.succeeded", context.correlationId, proposal.capability, 1, 1, 0)
    }
}

private class InMemoryActionExecutions : ActionExecutionRepository {
    private data class Key(val ownerId: UUID, val idempotencyKey: UUID)
    private val values = mutableMapOf<Key, ActionExecutionRecord>()

    override fun claim(ownerId: UUID, idempotencyKey: UUID, correlationId: UUID, requestHash: String, now: Instant): Boolean {
        val key = Key(ownerId, idempotencyKey)
        if (values.containsKey(key)) return false
        values[key] = ActionExecutionRecord(correlationId, requestHash, "pending", null)
        return true
    }

    override fun find(ownerId: UUID, idempotencyKey: UUID) = values[Key(ownerId, idempotencyKey)]
    override fun complete(ownerId: UUID, idempotencyKey: UUID, outcomeJson: String, now: Instant): Boolean {
        val key = Key(ownerId, idempotencyKey)
        val current = values[key] ?: return false
        values[key] = current.copy(status = "completed", outcomeJson = outcomeJson)
        return true
    }

    fun forcePending(ownerId: UUID, request: WebActionRequest) {
        val probe = InMemoryActionExecutions()
        val handler = CountingWebActionHandler()
        val service = WebActionService(probe, ActionOrchestrator(listOf(handler), ActionPolicyService(), ActivityService(EmptyWebActionActivityRepository())))
        service.execute(ownerId, request)
        val completed = probe.find(ownerId, request.idempotencyKey)!!
        values[Key(ownerId, request.idempotencyKey)] = completed.copy(status = "pending", outcomeJson = null)
    }
}

private class EmptyWebActionActivityRepository : ActivityEventRepository {
    override fun append(event: ActivityEvent) = event
    override fun findRecent(limit: Int) = emptyList<ActivityEvent>()
}
