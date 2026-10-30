package dev.kyrion.core.ai

import dev.kyrion.core.activity.*
import dev.kyrion.core.conversation.*
import dev.kyrion.core.security.RbacService
import org.springframework.stereotype.Service
import java.util.UUID
import java.io.IOException

data class AiGenerationRequest(
    val conversationId: UUID,
    val turnId: UUID,
    val locale: String = "en",
    val modelId: String? = null,
    val task: String = "chat",
    val cloudConsent: Boolean = false,
    val consentProvider: String? = null,
    val knowledgeEnabled: Boolean = false
)

data class PreparedAiGeneration(
    val actor: UUID,
    val request: AiGenerationRequest,
    val route: AiRouteRequest,
    val decision: AiRouteDecision,
    val catalog: AiCatalog,
    val conversation: Conversation,
    val context: ConversationContext,
    val reservation: AiReservation,
    val timeoutSeconds: Int,
    val knowledgeSources: List<dev.kyrion.core.knowledge.domain.KnowledgeSource> = emptyList()
)

@Service
class AiOrchestrationService(
    private val gateway: AiGateway, private val settings: AiSettingsService,
    private val usage: AiUsageService, private val conversations: ConversationRepository,
    private val context: ConversationController, private val cloud: CloudContextPolicy,
    private val rbac: RbacService, private val activity: ActivityService,
    private val knowledgeContext: dev.kyrion.core.context.KnowledgeContextAssembler
) {

    fun route(actor: UUID, request: AiRouteRequest): AiRouteDecision {
        rbac.require(actor, "conversations:create")
        return ModelRouter.select(
            gateway.catalog(),
            settings.repository.preferences(actor),
            settings.effectivePolicy(actor),
            request
        )
    }

    fun prepare(actor: UUID, request: AiGenerationRequest): PreparedAiGeneration {
        rbac.require(actor, "conversations:create")
        if (request.locale !in setOf("de", "en")) throw AiFailure("INVALID_REQUEST")
        val conversation =
            conversations.find(actor, request.conversationId) ?: throw AiFailure("CONVERSATION_NOT_FOUND", 404)
        val index = conversation.messages.indexOfFirst { it.id == request.turnId && it.role == "user" }
        if (index < 0) throw AiFailure("INVALID_REQUEST")
        val bounded = conversation.copy(messages = conversation.messages.take(index + 1))
        val route = AiRouteRequest(request.task, request.modelId, request.cloudConsent, request.consentProvider)
        val catalog = gateway.catalog()
        val policy = settings.effectivePolicy(actor)
        val decision = ModelRouter.select(catalog, settings.repository.preferences(actor), policy, route)
        // Current cloud consent releases only the current message, never documents.
        if (request.knowledgeEnabled && (!decision.model.local || decision.alternatives.any { !it.local }))
            throw AiFailure("CONTEXT_NOT_ALLOWED", 403)
        if (!decision.model.local) cloud.authorize(actor, decision.model.provider, "current_message", request.turnId)
        val limit = decision.model.contextLength?.let { it - decision.model.maxOutputTokens - 512 } ?: 3072
        if (limit < 128) throw AiFailure("CONTEXT_LIMIT_EXCEEDED")
        val knowledgeBudget = if (request.knowledgeEnabled) minOf(1024, limit / 3) else 0
        val sources = if (request.knowledgeEnabled)
            knowledgeContext.assemble(actor, bounded.messages.last().content, knowledgeBudget) else emptyList()
        val selected = context.generationContext(
            actor, bounded, request.turnId, !decision.model.local,
            minOf(3072, limit - knowledgeBudget)
        )
        // UTF-8 bytes plus bounded protocol/system overhead: deliberately conservative,
        // not an exact tokenizer count. Provider counters replace this after success.
        val estimate = aiJson.writeValueAsBytes(selected.messages).size.toLong() +
            aiJson.writeValueAsBytes(selected.usedMemories).size + aiJson.writeValueAsBytes(sources).size + 8192L
        val reservation = usage.reserve(actor, request.turnId, 0, decision.model, route, catalog, estimate)
        activity.record(
            ActivityCategory.INTEGRATION,
            "ai.route.selected",
            ActivityStatus.CONFIRMED,
            ActivityActorType.USER,
            "kyrion-core",
            decision.reason,
            actor.toString(),
            request.turnId,
            actor
        )
        return PreparedAiGeneration(
            actor,
            request,
            route,
            decision,
            catalog,
            bounded,
            selected,
            reservation,
            policy.maxTimeoutSeconds,
            sources
        )
    }

    fun stream(prepared: PreparedAiGeneration, emit: (String) -> Unit) {
        var reservation = prepared.reservation
        val expires =
            System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(prepared.timeoutSeconds.toLong())
        val candidates = listOf(prepared.decision.model) + prepared.decision.alternatives
        candidates.forEachIndexed { attempt, model ->
            if (attempt > 0) {
                try {
                    reservation = usage.reserve(
                        prepared.actor,
                        prepared.request.turnId,
                        attempt,
                        model,
                        prepared.route,
                        prepared.catalog,
                        prepared.reservation.inputEstimate
                    )
                } catch (failure: AiFailure) {
                    emit(aiJson.writeValueAsString(mapOf("type" to "error", "code" to failure.code)))
                    return
                }
                activity.record(
                    ActivityCategory.INTEGRATION,
                    "ai.route.fallback",
                    ActivityStatus.CONFIRMED,
                    ActivityActorType.USER,
                    "kyrion-core",
                    model.id,
                    prepared.actor.toString(),
                    prepared.request.turnId,
                    prepared.actor
                )
                emit(
                    aiJson.writeValueAsString(
                        mapOf(
                            "type" to "routing.fallback",
                            "profileId" to model.id,
                            "attempt" to attempt
                        )
                    )
                )
            }
            var visible = false
            var completed = false
            var completion: String? = null
            var sourceMessageId: String? = null
            var input: Long? = null;
            var output: Long? = null;
            var total: Long? = null
            var error: String? = null
            var explicitError = false
            val buffered = mutableListOf<String>()
            try {
                knowledgeContext.verify(prepared.actor, prepared.knowledgeSources)
                if (prepared.knowledgeSources.isNotEmpty() && model.contextLength != null &&
                    prepared.context.estimatedTokens + aiJson.writeValueAsBytes(prepared.knowledgeSources).size / 3 +
                    model.maxOutputTokens + 512 > model.contextLength) throw AiFailure("CONTEXT_LIMIT_EXCEEDED")
                val payload = aiJson.writeValueAsString(
                    mapOf(
                        "conversationId" to prepared.request.conversationId.toString(),
                        "modelId" to model.id,
                        "locale" to prepared.request.locale,
                        "interactionMode" to if (prepared.request.task == "voice") "voice" else "chat",
                        "cloudConsent" to (!model.local && prepared.request.cloudConsent),
                        "messages" to prepared.context.messages,
                        "memoryContext" to prepared.context.usedMemories,
                        "knowledgeContext" to prepared.knowledgeSources
                    )
                )
                if (attempt == 0) {
                    if (prepared.context.usedMemories.isNotEmpty()) emit(
                        aiJson.writeValueAsString(
                            mapOf(
                                "type" to "memory.used",
                                "items" to prepared.context.usedMemories
                            )
                        )
                    )
                    if (prepared.context.compacted) emit(
                        aiJson.writeValueAsString(
                            mapOf(
                                "type" to "context.compacted",
                                "estimatedTokens" to prepared.context.estimatedTokens,
                                "tokenBudget" to prepared.context.tokenBudget
                            )
                        )
                    )
                }
                val remaining = java.util.concurrent.TimeUnit.NANOSECONDS.toSeconds(expires - System.nanoTime()).toInt()
                if (remaining <= 0) throw AiFailure("REQUEST_TIMEOUT", 504)
                gateway.stream(payload, remaining) { raw ->
                    val event = aiJson.readTree(raw)
                    if (prepared.knowledgeSources.isNotEmpty() && event.path("type").asText().startsWith("message.")) {
                        val id = event.path("messageId").asText()
                        if (event.path("type").asText() == "message.started") {
                            if (sourceMessageId != null || runCatching { UUID.fromString(id) }.isFailure)
                                throw AiFailure("STREAM_FAILED", 502)
                            sourceMessageId = id
                        } else if (sourceMessageId == null || id != sourceMessageId) throw AiFailure("STREAM_FAILED", 502)
                    }
                    if (completed || error != null || buffered.size >= 100) throw AiFailure("STREAM_FAILED", 502)
                    when (event.path("type").asText()) {
                        "error" -> {
                            error = event.path("code").asText().takeIf { it in safeAiErrors }
                                ?: "STREAM_FAILED"; explicitError = true
                        }

                        "usage" -> {
                            val value = event.path("usage")
                            fun token(key: String) =
                                value.path(key).takeIf { it.isIntegralNumber && it.asLong() in 0..1_000_000_000L }
                                    ?.asLong()
                            input = token("inputTokens") ?: input; output = token("outputTokens") ?: output; total =
                                token("totalTokens") ?: total
                            if (visible) emit(raw) else buffered.add(raw)
                        }

                        "message.delta", "tool.call", "tool.result" -> {
                            if (!visible) {
                                buffered.forEach(emit); buffered.clear()
                            }
                            visible = true
                            // This surface never executes native tools; never fallback afterwards.
                            if (event.path("type").asText().startsWith("tool.")) throw AiFailure(
                                "TOOL_CALL_INVALID",
                                502
                            )
                            emit(raw)
                        }

                        "message.completed" -> {
                            if (prepared.knowledgeSources.isNotEmpty()) knowledgeContext.record(prepared.actor,
                                prepared.request.conversationId, UUID.fromString(event.path("messageId").asText()),
                                prepared.knowledgeSources)
                            completion = raw; completed = true
                        }

                        "message.started", "model.selected" -> {
                            if (event.path("type")
                                    .asText() == "message.started" && prepared.knowledgeSources.isNotEmpty()
                            ) {
                                buffered.add(raw)
                                buffered.add(
                                    aiJson.writeValueAsString(
                                        mapOf(
                                            "type" to "knowledge.sources",
                                            "messageId" to event.path("messageId").asText(),
                                            "items" to prepared.knowledgeSources
                                        )
                                    )
                                )
                                return@stream
                            }
                            if (visible) emit(raw) else {
                                if (buffered.size >= 100) throw AiFailure("STREAM_FAILED", 502); buffered.add(raw)
                            }
                        }

                        else -> throw AiFailure("STREAM_FAILED", 502)
                    }
                }
                if (!completed && error == null) error = "STREAM_FAILED"
            } catch (disconnected: IOException) {
                error = "REQUEST_ABORTED"
                throw disconnected
            } catch (failure: AiFailure) {
                error = failure.code
            } catch (_: Exception) {
                error = "STREAM_FAILED"
            } finally {
                usage.settle(prepared.actor, reservation, input, output, total, completed && error == null, error)
            }
            if (completed && error == null) {
                buffered.forEach(emit); completion?.let(emit); return
            }
            val code = error ?: "STREAM_FAILED"
            if (attempt < candidates.lastIndex && explicitError && ModelRouter.canFallback(
                    code,
                    visible
                )
            ) return@forEachIndexed
            buffered.forEach(emit)
            emit(aiJson.writeValueAsString(mapOf("type" to "error", "code" to code)))
            return
        }
    }

    fun voice(
        actor: UUID,
        conversationId: UUID,
        turnId: UUID,
        locale: String,
        knowledgeEnabled: Boolean = false,
        validateActive: () -> Unit = {}
    ): String {
        val prepared = prepare(
            actor,
            AiGenerationRequest(conversationId, turnId, locale, task = "voice", knowledgeEnabled = knowledgeEnabled)
        )
        val result = StringBuilder()
        stream(prepared) { raw ->
            validateActive()
            val event = aiJson.readTree(raw)
            if (event.path("type").asText() == "error") throw AiFailure(event.path("code").asText(), 503)
            if (event.path("type").asText() == "message.delta") result.append(event.path("delta").asText())
        }
        return result.toString().takeIf { it.isNotBlank() } ?: throw AiFailure("MODEL_UNAVAILABLE", 503)
    }
}
