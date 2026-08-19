package dev.kyrion.core.action

import dev.kyrion.core.capability.DeviceCommandArguments
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test
import org.mockito.Mockito.mock
import org.mockito.Mockito.verifyNoInteractions
import org.mockito.Mockito.`when`
import java.util.UUID

class WebActionIntentServiceTest {
    @Test
    fun `ordinary dialogue returns none and never executes`() {
        val actions = mock(WebActionService::class.java)
        val service = WebActionIntentService(FixedProposalProvider(ProposalResult.None), actions, ActionResultRenderer())

        val result = service.execute(UUID.randomUUID(), request())

        assertEquals("none", result.kind)
        assertNull(result.renderedText)
        verifyNoInteractions(actions)
    }

    @Test
    fun `proposal outage returns truthful text and never executes`() {
        val actions = mock(WebActionService::class.java)
        val service = WebActionIntentService(FixedProposalProvider(ProposalResult.Unavailable), actions, ActionResultRenderer())

        val result = service.execute(UUID.randomUUID(), request())

        assertEquals("unavailable", result.kind)
        assertEquals("proposal.unavailable", result.code)
        assertEquals("Ich konnte die Aktion gerade nicht sicher prüfen.", result.renderedText)
        verifyNoInteractions(actions)
    }

    @Test
    fun `confirmed device result is rendered in the requested locale`() {
        val owner = UUID.randomUUID()
        val target = UUID.randomUUID()
        val proposal = DeviceActionProposal(target, "power.set", DeviceCommandArguments(on = true))
        val request = request()
        val actionRequest = WebActionRequest(request.idempotencyKey, request.locale, proposal, request.conversationId)
        val actions = mock(WebActionService::class.java)
        `when`(actions.execute(owner, actionRequest)).thenReturn(ActionOutcome(
            ActionOutcomeStatus.SUCCEEDED, "action.succeeded", UUID.randomUUID(), "power.set", 1, 1, 0,
            listOf(ActionTargetOutcome(target, "Bürolampe", "succeeded")),
        ))

        val result = WebActionIntentService(FixedProposalProvider(ProposalResult.Proposed(proposal)), actions, ActionResultRenderer())
            .execute(owner, request)

        assertEquals("action", result.kind)
        assertEquals("„Bürolampe“ ist jetzt eingeschaltet.", result.renderedText)
    }

    private fun request() = WebActionIntentRequest(UUID.randomUUID(), "Mach das Licht an", "de", conversationId = UUID.randomUUID())
}

private class FixedProposalProvider(private val result: ProposalResult) : DeviceProposalProvider {
    override fun propose(ownerId: UUID, message: String, locale: String, priorMessages: List<ActionPriorMessage>) = result
}
