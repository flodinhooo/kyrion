package dev.kyrion.core.voice

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import java.util.UUID

class VoiceResponsePlanTest {
    private val registry = VoiceResponsePolicyRegistry()
    private val context = VoiceResponseContext(
        UUID.fromString("00000000-0000-0000-0000-000000000001"),
        UUID.fromString("00000000-0000-0000-0000-000000000002"),
        UUID.fromString("00000000-0000-0000-0000-000000000003"),
        "de",
    )

    @Test
    fun `registry dispatches every initial outcome category`() {
        assertThat(registry.resolve(SessionGreetingOutcome, context)).isInstanceOf(FixedResponsePlan::class.java)
        assertThat(registry.resolve(SessionFarewellOutcome, context)).isInstanceOf(FixedResponsePlan::class.java)
        assertThat(registry.resolve(DialogueAcknowledgedOutcome, context)).isInstanceOf(FixedResponsePlan::class.java)
        assertThat(registry.resolve(ActionProcessingOutcome, context)).isInstanceOf(FixedResponsePlan::class.java)
        assertThat(
            registry.resolve(CommandExecutionOutcome(true, true, "Gamingraum"), context),
        ).isInstanceOf(FixedResponsePlan::class.java)
        assertThat(registry.resolve(DynamicDialogueOutcome("Eine freie Antwort."), context))
            .isInstanceOf(DynamicResponsePlan::class.java)
    }

    @Test
    fun `variant selection is deterministic for the same response context`() {
        val first = registry.resolve(SessionFarewellOutcome, context) as FixedResponsePlan
        val second = registry.resolve(SessionFarewellOutcome, context) as FixedResponsePlan

        assertThat(second.variantId).isEqualTo(first.variantId)
        assertThat(second.renderedText).isEqualTo(first.renderedText)
    }

    @Test
    fun `catalog is complete for German and English`() {
        VoiceResponseCatalog().validateLocaleCompleteness()
        val english = context.copy(locale = "en")

        assertThat(registry.resolve(SessionGreetingOutcome, english).renderedText).isNotBlank()
        assertThat(
            registry.resolve(CommandExecutionOutcome(true, false, "Desk lamp"), english).renderedText,
        ).isNotBlank()
    }

    @Test
    fun `template slots reject unknown types and unsafe values`() {
        val catalog = VoiceResponseCatalog()

        assertThatThrownBy {
            catalog.render(
                "command.succeeded",
                "de",
                mapOf("targetName" to VoiceResponseSlot(VoiceResponseSlotType.entityName, "\u0000")),
            )
        }.isInstanceOf(VoiceResponseValidationException::class.java)
        assertThatThrownBy { catalog.render("command.succeeded", "de", emptyMap()) }
            .isInstanceOf(VoiceResponseValidationException::class.java)
    }

    @Test
    fun `command success requires a Core-confirmed outcome`() {
        assertThatThrownBy {
            registry.resolve(CommandExecutionOutcome(false, true, "Gamingraum"), context)
        }.isInstanceOf(VoiceResponseValidationException::class.java)
            .hasMessage("COMMAND_OUTCOME_UNCONFIRMED")
    }

    @Test
    fun `fixed command outcome is deterministic for the same turn`() {
        val first = registry.resolve(
            CommandExecutionOutcome(true, true, "Gamingraum"),
            context,
        ) as FixedResponsePlan
        val repeated = registry.resolve(
            CommandExecutionOutcome(true, true, "Gamingraum"),
            context,
        ) as FixedResponsePlan

        assertThat(repeated.variantId).isEqualTo(first.variantId)
        assertThat(repeated.renderedText).isEqualTo(first.renderedText)
    }

    @Test
    fun `invalid or privileged LLM proposals are rejected`() {
        assertThatThrownBy {
            registry.validateProposal(
                VoiceResponseProposal("catalog", "command.succeeded"),
            )
        }.isInstanceOf(VoiceResponseValidationException::class.java)
        assertThatThrownBy {
            registry.validateProposal(
                VoiceResponseProposal(
                    "catalog",
                    "dialogue.acknowledged",
                    slots = mapOf(
                        "targetName" to VoiceResponseSlot(
                            VoiceResponseSlotType.entityName,
                            "invented",
                        ),
                    ),
                ),
            )
        }.isInstanceOf(VoiceResponseValidationException::class.java)
    }

    @Test
    fun `valid dynamic proposal preserves the dynamic fallback`() {
        val outcome = registry.validateProposal(
            VoiceResponseProposal("dynamic", text = "Eine kurze freie Antwort."),
        )
        val plan = registry.resolve(outcome, context)

        assertThat(plan).isInstanceOf(DynamicResponsePlan::class.java)
        assertThat(plan.renderedText).isEqualTo("Eine kurze freie Antwort.")
    }
}
