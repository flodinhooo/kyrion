package dev.kyrion.core.ai

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import java.math.BigDecimal

class ModelRouterTest {
    private fun local(id: String, tools: Boolean = false) =
        AiModel(id, capabilities = listOf("chat", "streaming") + if (tools) listOf("tools") else emptyList())

    private fun cloud(id: String, provider: String) =
        AiModel(id, provider = provider, local = false, capabilities = listOf("chat", "streaming"))

    private val catalog = AiCatalog(
        "local-a",
        listOf(local("local-b", true), cloud("gpt", "openai"), local("local-a"), cloud("claude", "anthropic"))
    )

    @Test
    fun `safe defaults and tie breaking are local deterministic and order independent`() {
        val first = ModelRouter.select(catalog, AiPreferences(), AiPolicy(), AiRouteRequest())
        assertEquals("local-a", first.model.id)
        assertEquals(
            first.model,
            ModelRouter.select(
                catalog.copy(models = catalog.models.reversed()),
                AiPreferences(),
                AiPolicy(),
                AiRouteRequest()
            ).model
        )
        assertTrue(first.rejected.containsKey("gpt"))
    }

    @Test
    fun `user chat voice preferences and capability requirements select known eligible models`() {
        val prefs = AiPreferences(chatProfileId = "local-b", voiceProfileId = "local-b")
        assertEquals("local-b", ModelRouter.select(catalog, prefs, AiPolicy(), AiRouteRequest()).model.id)
        assertEquals("local-b", ModelRouter.select(catalog, prefs, AiPolicy(), AiRouteRequest(task = "voice")).model.id)
        assertEquals(
            "local-b",
            ModelRouter.select(catalog, AiPreferences(), AiPolicy(), AiRouteRequest(task = "tools")).model.id
        )
        assertEquals(
            "local-a",
            ModelRouter.select(
                catalog,
                prefs.copy(voiceProfileId = "missing"),
                AiPolicy(),
                AiRouteRequest(task = "voice")
            ).model.id
        )
    }

    @Test
    fun `administrator allowlists priorities and selection override user preferences`() {
        val policy = AiPolicy(allowUserSelection = false, priorities = listOf("local-a"))
        val decision = ModelRouter.select(
            catalog,
            AiPreferences(chatProfileId = "local-b"),
            policy,
            AiRouteRequest(modelId = "local-b")
        )
        assertEquals("local-a", decision.model.id)
        assertEquals("administrator_policy", decision.reason)
        assertThrows<AiFailure> {
            ModelRouter.select(
                catalog,
                AiPreferences(),
                AiPolicy(allowedProfiles = listOf("local-a")),
                AiRouteRequest(modelId = "local-b")
            )
        }
    }

    @Test
    fun `cloud needs all three policy preference and exact provider consent gates`() {
        val policy = AiPolicy(allowedProviders = listOf("ollama", "openai"), allowCloud = true)
        val prefs = AiPreferences(localOnly = false, allowedCloudProviders = listOf("openai"), chatProfileId = "gpt")
        val request = AiRouteRequest(modelId = "gpt", cloudConsent = true, consentProvider = "openai")
        assertEquals("gpt", ModelRouter.select(catalog, prefs, policy, request).model.id)
        assertThrows<AiFailure> { ModelRouter.select(catalog, prefs, policy, request.copy(cloudConsent = false)) }
        assertThrows<AiFailure> {
            ModelRouter.select(
                catalog,
                prefs,
                policy,
                request.copy(consentProvider = "anthropic")
            )
        }
        assertThrows<AiFailure> { ModelRouter.select(catalog, prefs.copy(localOnly = true), policy, request) }
        assertThrows<AiFailure> { ModelRouter.select(catalog, prefs, policy.copy(allowCloud = false), request) }
        assertThrows<AiFailure> { ModelRouter.select(catalog, prefs, policy, request.copy(task = "voice")) }
        assertTrue(ModelRouter.select(catalog, prefs, policy, request.copy(modelId = null)).model.local)
    }

    @Test
    fun `explicit task rules outrank preferences and unavailable profiles are excluded`() {
        assertEquals(
            "local-b",
            ModelRouter.select(
                catalog,
                AiPreferences(),
                AiPolicy(taskProfiles = mapOf("code" to listOf("local-b"))),
                AiRouteRequest(task = "code")
            ).model.id
        )
        val changed =
            catalog.copy(models = catalog.models.map { if (it.id == "local-a") it.copy(available = false) else it })
        assertEquals("local-b", ModelRouter.select(changed, AiPreferences(), AiPolicy(), AiRouteRequest()).model.id)
    }

    @Test
    fun `fallback is opt in allowlisted and cannot cross a privacy boundary`() {
        val policy = AiPolicy(
            allowFallback = true,
            fallbackProfiles = listOf("gpt", "local-b"),
            allowCloud = true,
            allowedProviders = listOf("ollama", "openai")
        )
        val prefs = AiPreferences(allowFallback = true, localOnly = false, allowedCloudProviders = listOf("openai"))
        assertEquals(
            listOf("local-b"),
            ModelRouter.select(
                catalog,
                prefs,
                policy,
                AiRouteRequest(cloudConsent = true, consentProvider = "openai")
            ).alternatives.map { it.id })
        assertTrue(
            ModelRouter.select(
                catalog,
                prefs.copy(allowFallback = false),
                policy,
                AiRouteRequest()
            ).alternatives.isEmpty()
        )
        for (code in listOf("REQUEST_TIMEOUT", "STREAM_FAILED", "REQUEST_ABORTED", "TOOL_CALL_INVALID")) assertFalse(
            ModelRouter.canFallback(code, false)
        )
        assertFalse(ModelRouter.canFallback("MODEL_UNAVAILABLE", true))
        assertTrue(ModelRouter.canFallback("MODEL_UNAVAILABLE", false))
    }

    @Test
    fun `costs are explicit estimates and administrator token ceiling cannot be raised by user`() {
        assertEquals(
            100L,
            effectiveTokenLimit(AiPreferences(monthlyTokenLimit = 1000), AiPolicy(monthlyTokenLimit = 100))
        )
        assertNull(estimateAiCost(100, 100, local("unknown")))
        val priced = local("priced").copy(
            inputCostPerMillion = BigDecimal("2"),
            outputCostPerMillion = BigDecimal("4"),
            currency = "CHF"
        )
        assertEquals(BigDecimal("0.00060000"), estimateAiCost(100, 100, priced))
    }
}
