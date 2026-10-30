package dev.kyrion.core.ai

import java.math.BigDecimal

data class AiPreferences(
    val chatProfileId: String? = null,
    val voiceProfileId: String? = null,
    val preferredProvider: String? = null,
    val localOnly: Boolean = true,
    val allowedCloudProviders: List<String> = emptyList(),
    val routingPreference: String = "local_first",
    val allowFallback: Boolean = false,
    val monthlyTokenLimit: Long? = null,
)

data class AiPolicy(
    val allowedProviders: List<String> = listOf("ollama"),
    val allowCloud: Boolean = false,
    val allowedProfiles: List<String> = emptyList(),
    val allowUserSelection: Boolean = true,
    val cloudDataScope: String = "current_message",
    val priorities: List<String> = emptyList(),
    val taskProfiles: Map<String, List<String>> = emptyMap(),
    val allowFallback: Boolean = false,
    val fallbackProfiles: List<String> = emptyList(),
    val monthlyTokenLimit: Long? = null,
    val monthlyCostLimit: BigDecimal? = null,
    val currency: String? = null,
    val maxRequestTokens: Long = 65536,
    val maxTimeoutSeconds: Int = 180,
)

data class AiModel(
    val id: String, val provider: String = "ollama", val modelId: String? = null,
    val label: String = "", val local: Boolean = true, val enabled: Boolean = true,
    val available: Boolean = true, val capabilities: List<String> = emptyList(),
    val maxOutputTokens: Int = 1024, val contextLength: Int? = null,
    val inputCostPerMillion: BigDecimal? = null, val outputCostPerMillion: BigDecimal? = null,
    val currency: String? = null,
)

data class AiCatalog(val defaultModelId: String, val models: List<AiModel>, val voiceProfileId: String? = null)
data class AiRouteRequest(
    val task: String = "chat", val modelId: String? = null,
    val cloudConsent: Boolean = false, val consentProvider: String? = null,
)

data class AiRouteDecision(
    val model: AiModel,
    val reason: String,
    val alternatives: List<AiModel>,
    val rejected: Map<String, String>
)

class AiFailure(val code: String, val httpStatus: Int = 400) : RuntimeException(code)

/** Pure deterministic policy; no provider calls, persistence, prompts or side effects. */
object ModelRouter {
    val providers = setOf("ollama", "openai", "anthropic", "gemini")
    val tasks = setOf("chat", "voice", "analysis", "code", "tools")

    fun select(catalog: AiCatalog, prefs: AiPreferences, policy: AiPolicy, request: AiRouteRequest): AiRouteDecision {
        if (request.task !in tasks) throw AiFailure("INVALID_REQUEST")
        val rejected = linkedMapOf<String, String>()
        val required = setOf("chat", "streaming") + if (request.task == "tools") setOf("tools") else emptySet()
        fun denial(model: AiModel): String? = when {
            model.provider !in providers || model.local != (model.provider == "ollama") -> "MODEL_INVALID"
            !model.enabled || !model.available -> "MODEL_UNAVAILABLE"
            model.provider !in policy.allowedProviders -> "PROVIDER_BLOCKED"
            policy.allowedProfiles.isNotEmpty() && model.id !in policy.allowedProfiles -> "MODEL_BLOCKED"
            !model.capabilities.containsAll(required) -> "CAPABILITY_UNSUPPORTED"
            !model.local && (request.task == "voice" || prefs.localOnly || !policy.allowCloud) -> "CLOUD_NOT_ALLOWED"
            !model.local && model.provider !in prefs.allowedCloudProviders -> "CLOUD_NOT_ALLOWED"
            !model.local && (!request.cloudConsent || request.consentProvider != model.provider) -> "CLOUD_CONSENT_REQUIRED"
            else -> null
        }

        val eligible = catalog.models.filter { model ->
            val code = denial(model)
            if (code != null) rejected[model.id] = code
            code == null
        }
        val requested = request.modelId?.takeUnless { it == "auto" }
        if (requested != null && policy.allowUserSelection) {
            val selected = eligible.firstOrNull { it.id == requested }
                ?: throw AiFailure(rejected[requested] ?: "MODEL_UNAVAILABLE", 403)
            return AiRouteDecision(selected, "explicit_profile", fallbacks(selected, eligible, prefs, policy), rejected)
        }
        val preferred = if (request.task == "voice") prefs.voiceProfileId else prefs.chatProfileId
        val taskPriority = policy.taskProfiles[request.task].orEmpty()
        fun priority(id: String, list: List<String>) = list.indexOf(id).takeIf { it >= 0 } ?: Int.MAX_VALUE
        val sorted = eligible.sortedWith(
            compareBy<AiModel>(
                { if (it.local) 0 else 1 }, // Local-first always precedes cloud preference.
                { priority(it.id, taskPriority) },
                { priority(it.id, policy.priorities) },
                { if (policy.allowUserSelection && it.id == preferred) 0 else 1 },
                { if (policy.allowUserSelection && it.provider == prefs.preferredProvider) 0 else 1 },
                {
                    if (prefs.routingPreference == "economy") it.inputCostPerMillion
                        ?: BigDecimal("1E20") else BigDecimal.ZERO
                },
                {
                    if (it.id == (if (request.task == "voice") catalog.voiceProfileId
                            ?: catalog.defaultModelId else catalog.defaultModelId)
                    ) 0 else 1
                },
                { it.id },
            )
        )
        val selected = sorted.firstOrNull() ?: throw AiFailure("NO_ELIGIBLE_MODEL", 503)
        return AiRouteDecision(
            selected, if (!policy.allowUserSelection) "administrator_policy" else "deterministic_local_first",
            fallbacks(selected, sorted, prefs, policy), rejected
        )
    }

    private fun fallbacks(
        selected: AiModel,
        eligible: List<AiModel>,
        prefs: AiPreferences,
        policy: AiPolicy
    ): List<AiModel> {
        if (!prefs.allowFallback || !policy.allowFallback) return emptyList()
        return policy.fallbackProfiles.mapNotNull { id ->
            eligible.firstOrNull {
                it.id == id && it.id != selected.id &&
                    it.local == selected.local && (it.local || it.provider == selected.provider)
            }
        }.distinctBy { it.id }
    }

    fun canFallback(code: String, visibleOutput: Boolean): Boolean =
        !visibleOutput && code in setOf("MODEL_UNAVAILABLE", "RATE_LIMITED", "PROVIDER_NOT_CONFIGURED")
}
