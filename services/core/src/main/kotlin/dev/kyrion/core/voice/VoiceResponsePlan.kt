package dev.kyrion.core.voice

import org.springframework.stereotype.Service
import java.nio.ByteBuffer
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.util.UUID
import kotlin.reflect.KClass

const val VOICE_RESPONSE_CATALOG_REVISION = "voice-responses-v1"
const val VELORA_VOICE_PROFILE_ID = "velora"
const val VELORA_VOICE_PROFILE_REVISION =
    "d2afdc5faa3fb6cc41756daaaac3db63c30679e3bcd3e87f6dab0055d08dad09"

sealed interface DialogueOutcome
data object SessionGreetingOutcome : DialogueOutcome
data object SessionFarewellOutcome : DialogueOutcome
data object DialogueAcknowledgedOutcome : DialogueOutcome
data object ActionProcessingOutcome : DialogueOutcome
data class CommandExecutionOutcome(
    val executionConfirmed: Boolean,
    val succeeded: Boolean,
    val targetName: String,
) : DialogueOutcome
data class DynamicDialogueOutcome(val text: String) : DialogueOutcome

data class VoiceResponseContext(
    val ownerId: UUID,
    val sessionId: UUID,
    val turnId: UUID,
    val locale: String,
    val voiceProfileId: String = VELORA_VOICE_PROFILE_ID,
    val voiceProfileRevision: String = VELORA_VOICE_PROFILE_REVISION,
)

enum class VoiceResponseSlotType { entityName }

data class VoiceResponseSlot(val type: VoiceResponseSlotType, val value: String)

sealed interface VoiceResponsePlan {
    val kind: String
    val responseType: String
    val locale: String
    val voiceProfileId: String
    val voiceProfileRevision: String
    val catalogRevision: String
    val renderedText: String
}

data class FixedResponsePlan(
    override val kind: String = "fixed",
    override val responseType: String,
    override val locale: String,
    override val voiceProfileId: String,
    override val voiceProfileRevision: String,
    override val catalogRevision: String,
    override val renderedText: String,
    val responseKey: String,
    val variantId: String,
) : VoiceResponsePlan

data class TemplateResponsePlan(
    override val kind: String = "template",
    override val responseType: String,
    override val locale: String,
    override val voiceProfileId: String,
    override val voiceProfileRevision: String,
    override val catalogRevision: String,
    override val renderedText: String,
    val templateKey: String,
    val slots: Map<String, VoiceResponseSlot>,
    val cacheScope: String,
) : VoiceResponsePlan

data class DynamicResponsePlan(
    override val kind: String = "dynamic",
    override val responseType: String = "dialogue.dynamic",
    override val locale: String,
    override val voiceProfileId: String,
    override val voiceProfileRevision: String,
    override val catalogRevision: String,
    override val renderedText: String,
) : VoiceResponsePlan

data class VoiceResponseVariant(val id: String, val text: String)

data class VoiceResponseTemplate(
    val requiredSlots: Map<String, VoiceResponseSlotType>,
    val texts: Map<String, String>,
)

class VoiceResponseCatalog {
    val revision = VOICE_RESPONSE_CATALOG_REVISION

    private val fixed = mapOf(
        "session.greeting" to mapOf(
            "de" to listOf(
                VoiceResponseVariant("neutral-01", "Hallo."),
                VoiceResponseVariant("warm-01", "Hallo, schön dich zu hören."),
                VoiceResponseVariant("friendly-01", "Hey, schön, dass du da bist."),
                VoiceResponseVariant("ready-01", "Hallo, ich bin bereit."),
                VoiceResponseVariant("warm-02", "Schön, von dir zu hören."),
                VoiceResponseVariant("helpful-01", "Hey, was kann ich für dich tun?"),
            ),
            "en" to listOf(
                VoiceResponseVariant("neutral-01", "Hello."),
                VoiceResponseVariant("warm-01", "Hello, good to hear you."),
                VoiceResponseVariant("friendly-01", "Hey, it's good to have you here."),
                VoiceResponseVariant("ready-01", "Hello, I'm ready."),
                VoiceResponseVariant("warm-02", "Good to hear from you."),
                VoiceResponseVariant("helpful-01", "Hey, what can I do for you?"),
            ),
        ),
        "session.farewell" to mapOf(
            "de" to listOf(
                VoiceResponseVariant("neutral-01", "Bis später."),
                VoiceResponseVariant("warm-01", "Mach's gut."),
            ),
            "en" to listOf(
                VoiceResponseVariant("neutral-01", "Talk to you later."),
                VoiceResponseVariant("warm-01", "Take care."),
            ),
        ),
        "dialogue.acknowledged" to mapOf(
            "de" to listOf(
                VoiceResponseVariant("neutral-01", "Okay."),
                VoiceResponseVariant("neutral-02", "Alles klar."),
            ),
            "en" to listOf(
                VoiceResponseVariant("neutral-01", "Okay."),
                VoiceResponseVariant("neutral-02", "Got it."),
            ),
        ),
        "action.processing" to mapOf(
            "de" to listOf(
                VoiceResponseVariant("neutral-01", "Klar, gib mir einen Augenblick."),
                VoiceResponseVariant("neutral-02", "Alles klar, ich kümmere mich darum."),
                VoiceResponseVariant("neutral-03", "Verstanden, einen Moment bitte."),
                VoiceResponseVariant("warm-01", "Gerne, ich kümmere mich darum."),
            ),
            "en" to listOf(
                VoiceResponseVariant("neutral-01", "Sure, give me a moment."),
                VoiceResponseVariant("neutral-02", "All right, I'm taking care of it."),
                VoiceResponseVariant("neutral-03", "Understood, one moment please."),
                VoiceResponseVariant("warm-01", "Of course, I'm taking care of it."),
            ),
        ),
        "command.succeeded" to mapOf(
            "de" to listOf(
                VoiceResponseVariant("neutral-01", "Erledigt."),
                VoiceResponseVariant("neutral-02", "Ist erledigt."),
            ),
            "en" to listOf(
                VoiceResponseVariant("neutral-01", "Done."),
                VoiceResponseVariant("neutral-02", "It's done."),
            ),
        ),
        "command.failed" to mapOf(
            "de" to listOf(
                VoiceResponseVariant("neutral-01", "Das hat nicht funktioniert."),
                VoiceResponseVariant("neutral-02", "Der Befehl ist fehlgeschlagen."),
            ),
            "en" to listOf(
                VoiceResponseVariant("neutral-01", "That didn't work."),
                VoiceResponseVariant("neutral-02", "The command failed."),
            ),
        ),
    )

    private val templates = mapOf(
        "command.succeeded" to VoiceResponseTemplate(
            mapOf("targetName" to VoiceResponseSlotType.entityName),
            mapOf(
                "de" to "{targetName} wurde erfolgreich aktualisiert.",
                "en" to "{targetName} was updated successfully.",
            ),
        ),
        "command.failed" to VoiceResponseTemplate(
            mapOf("targetName" to VoiceResponseSlotType.entityName),
            mapOf(
                "de" to "{targetName} konnte nicht aktualisiert werden.",
                "en" to "{targetName} could not be updated.",
            ),
        ),
    )

    init {
        val supportedLocales = setOf("de", "en")
        require(fixed.values.all { it.keys == supportedLocales && it.values.all(List<*>::isNotEmpty) })
        require(templates.values.all { it.texts.keys == supportedLocales })
    }

    fun variants(responseKey: String, locale: String): List<VoiceResponseVariant> =
        fixed[responseKey]?.get(locale) ?: throw VoiceResponseValidationException("UNKNOWN_RESPONSE")

    fun render(templateKey: String, locale: String, slots: Map<String, VoiceResponseSlot>): String {
        val template = templates[templateKey]
            ?: throw VoiceResponseValidationException("UNKNOWN_TEMPLATE")
        if (slots.mapValues { it.value.type } != template.requiredSlots) {
            throw VoiceResponseValidationException("INVALID_SLOTS")
        }
        val text = template.texts[locale]
            ?: throw VoiceResponseValidationException("UNSUPPORTED_LOCALE")
        return slots.entries.fold(text) { rendered, (name, slot) ->
            rendered.replace("{$name}", validateSlot(slot))
        }
    }

    fun validateLocaleCompleteness() = Unit

    private fun validateSlot(slot: VoiceResponseSlot): String {
        val value = slot.value.trim()
        if (value.isEmpty() || value.length > 120 || value.any { it.isISOControl() }) {
            throw VoiceResponseValidationException("INVALID_SLOT_VALUE")
        }
        return value
    }
}

interface VoiceResponseResolver<T : DialogueOutcome> {
    val outcomeType: KClass<T>
    fun resolve(outcome: T, context: VoiceResponseContext): VoiceResponsePlan
}

private class FixedOutcomeResolver<T : DialogueOutcome>(
    override val outcomeType: KClass<T>,
    private val responseKey: String,
    private val catalog: VoiceResponseCatalog,
) : VoiceResponseResolver<T> {
    override fun resolve(outcome: T, context: VoiceResponseContext): VoiceResponsePlan {
        val variants = catalog.variants(responseKey, context.locale)
        val variant = variants[deterministicVariantIndex(context, responseKey, variants.size)]
        return FixedResponsePlan(
            responseType = responseKey,
            responseKey = responseKey,
            variantId = variant.id,
            locale = context.locale,
            voiceProfileId = context.voiceProfileId,
            voiceProfileRevision = context.voiceProfileRevision,
            catalogRevision = catalog.revision,
            renderedText = variant.text,
        )
    }
}

private class CommandOutcomeResolver(
    private val catalog: VoiceResponseCatalog,
) : VoiceResponseResolver<CommandExecutionOutcome> {
    override val outcomeType = CommandExecutionOutcome::class

    override fun resolve(
        outcome: CommandExecutionOutcome,
        context: VoiceResponseContext,
    ): VoiceResponsePlan {
        if (!outcome.executionConfirmed) {
            throw VoiceResponseValidationException("COMMAND_OUTCOME_UNCONFIRMED")
        }
        val responseKey = if (outcome.succeeded) "command.succeeded" else "command.failed"
        val variants = catalog.variants(responseKey, context.locale)
        val variant = variants[deterministicVariantIndex(context, responseKey, variants.size)]
        return FixedResponsePlan(
            responseType = responseKey,
            responseKey = responseKey,
            variantId = variant.id,
            locale = context.locale,
            voiceProfileId = context.voiceProfileId,
            voiceProfileRevision = context.voiceProfileRevision,
            catalogRevision = catalog.revision,
            renderedText = variant.text,
        )
    }
}

private class DynamicOutcomeResolver(
    private val catalog: VoiceResponseCatalog,
) : VoiceResponseResolver<DynamicDialogueOutcome> {
    override val outcomeType = DynamicDialogueOutcome::class

    override fun resolve(
        outcome: DynamicDialogueOutcome,
        context: VoiceResponseContext,
    ): VoiceResponsePlan {
        val text = outcome.text.trim()
        if (text.isEmpty()) throw VoiceResponseValidationException("DYNAMIC_TEXT_EMPTY")
        return DynamicResponsePlan(
            locale = context.locale,
            voiceProfileId = context.voiceProfileId,
            voiceProfileRevision = context.voiceProfileRevision,
            catalogRevision = catalog.revision,
            renderedText = text,
        )
    }
}

@Service
class VoiceResponsePolicyRegistry {
    private val catalog = VoiceResponseCatalog()
    private val resolvers: Map<KClass<out DialogueOutcome>, VoiceResponseResolver<out DialogueOutcome>> =
        listOf(
            FixedOutcomeResolver(SessionGreetingOutcome::class, "session.greeting", catalog),
            FixedOutcomeResolver(SessionFarewellOutcome::class, "session.farewell", catalog),
            FixedOutcomeResolver(
                DialogueAcknowledgedOutcome::class,
                "dialogue.acknowledged",
                catalog,
            ),
            FixedOutcomeResolver(ActionProcessingOutcome::class, "action.processing", catalog),
            CommandOutcomeResolver(catalog),
            DynamicOutcomeResolver(catalog),
        ).associateBy { it.outcomeType }

    @Suppress("UNCHECKED_CAST")
    fun resolve(outcome: DialogueOutcome, context: VoiceResponseContext): VoiceResponsePlan {
        if (context.locale !in setOf("de", "en")) {
            throw VoiceResponseValidationException("UNSUPPORTED_LOCALE")
        }
        val resolver = resolvers[outcome::class]
            as? VoiceResponseResolver<DialogueOutcome>
            ?: throw VoiceResponseValidationException("OUTCOME_UNSUPPORTED")
        return resolver.resolve(outcome, context)
    }

    fun validateProposal(proposal: VoiceResponseProposal): DialogueOutcome = when {
        proposal.mode == "catalog" &&
            proposal.responseType == "dialogue.acknowledged" &&
            proposal.text == null && proposal.slots.isEmpty() -> DialogueAcknowledgedOutcome
        proposal.mode == "dynamic" && proposal.responseType == null &&
            !proposal.text.isNullOrBlank() && proposal.slots.isEmpty() ->
            DynamicDialogueOutcome(proposal.text)
        else -> throw VoiceResponseValidationException("INVALID_PROPOSAL")
    }
}

data class VoiceResponseProposal(
    val mode: String,
    val responseType: String? = null,
    val text: String? = null,
    val slots: Map<String, VoiceResponseSlot> = emptyMap(),
)

class VoiceResponseValidationException(val code: String) : RuntimeException(code)

private fun deterministicVariantIndex(
    context: VoiceResponseContext,
    responseKey: String,
    variantCount: Int,
): Int {
    val input = listOf(
        context.ownerId,
        context.sessionId,
        context.turnId,
        responseKey,
        VOICE_RESPONSE_CATALOG_REVISION,
    ).joinToString(":")
    val digest = MessageDigest.getInstance("SHA-256")
        .digest(input.toByteArray(StandardCharsets.UTF_8))
    return Math.floorMod(ByteBuffer.wrap(digest).int, variantCount)
}

private fun ownerCacheScope(ownerId: UUID): String = MessageDigest.getInstance("SHA-256")
    .digest(ownerId.toString().toByteArray(StandardCharsets.UTF_8))
    .joinToString("") { byte -> "%02x".format(byte) }
