package dev.kyrion.core.conversation

import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.memory.MemoryContextSelector
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.mockito.Mockito.*
import org.springframework.mock.web.MockHttpServletRequest
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

class CloudContextPolicyTest {
    private val activity = mock(ActivityService::class.java)
    private val actor = UUID.randomUUID()

    @Test
    fun `cloud is disabled by default and requires exact per-request consent`() {
        CloudContextPolicy(activity).authorize(actor, null, null, UUID.randomUUID())
        assertThrows<CloudProcessingDenied> {
            CloudContextPolicy(activity).authorize(actor, "openai", "current_message", UUID.randomUUID())
        }
        for (provider in listOf("openai", "anthropic", "gemini")) {
            assertThrows<CloudProcessingDenied> {
                CloudContextPolicy(activity, true).authorize(actor, provider, null, UUID.randomUUID())
            }
        }
        assertThrows<CloudProcessingDenied> {
            CloudContextPolicy(activity, true).authorize(actor, "untrusted", "current_message", UUID.randomUUID())
        }
        verifyNoInteractions(activity)
    }

    @Test
    fun `approved cloud context excludes all persisted history and never selects memories`() {
        val repository = mock(ConversationRepository::class.java)
        val memories = mock(MemoryContextSelector::class.java)
        val now = Instant.parse("2026-10-30T12:00:00Z")
        val clock = Clock.fixed(now, ZoneOffset.UTC)
        val id = UUID.randomUUID()
        val message = ConversationMessageRequest(UUID.randomUUID(), "user", "Current synthetic message", now)
        val stored = Conversation(
            id, "Local title", now, now, listOf(
                ConversationMessage(UUID.randomUUID(), "assistant", "PRIVATE HISTORICAL SUMMARY", now),
                ConversationMessage(message.id, "user", message.content, now),
            )
        )
        `when`(repository.startTurn(actor, id, "Local title", stored.messages.last(), now)).thenReturn(stored)
        val controller = ConversationController(repository, memories, clock, CloudContextPolicy(activity, true))
        val request = MockHttpServletRequest().apply { setAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE, actor) }
        val result = controller.startTurn(
            id, StartConversationTurnRequest(
                "Local title", message, externalProvider = "gemini", externalConsent = "current_message",
            ), request
        )
        assertEquals(listOf(ConversationContextMessage("user", message.content)), result.messages)
        assertTrue(result.usedMemories.isEmpty())
        assertFalse(result.compacted)
        verifyNoInteractions(memories)
        val audit = mockingDetails(activity).invocations.single()
        assertEquals("ai.cloud.context.authorized", audit.arguments[1])
        assertFalse(audit.arguments.joinToString().contains(message.content))
    }

    @Test
    fun `denial happens before turn persistence or memory access`() {
        val repository = mock(ConversationRepository::class.java)
        val memories = mock(MemoryContextSelector::class.java)
        val controller = ConversationController(repository, memories, Clock.systemUTC(), CloudContextPolicy(activity))
        val request = MockHttpServletRequest().apply { setAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE, actor) }
        assertThrows<CloudProcessingDenied> {
            controller.startTurn(
                UUID.randomUUID(), StartConversationTurnRequest(
                    "Test",
                    ConversationMessageRequest(UUID.randomUUID(), "user", "Test", Instant.now()),
                    externalProvider = "openai", externalConsent = "current_message"
                ), request
            )
        }
        verifyNoInteractions(repository, memories)
    }
}
