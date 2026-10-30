package dev.kyrion.core.ai

import com.fasterxml.jackson.databind.DeserializationFeature
import com.fasterxml.jackson.databind.MapperFeature
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.*
import dev.kyrion.core.security.RbacService
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.math.BigDecimal
import java.math.RoundingMode
import java.time.YearMonth
import java.time.ZoneOffset
import java.util.UUID

internal val aiJson = jacksonObjectMapper().findAndRegisterModules()
    .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, false)
internal val strictAiJson = jacksonObjectMapper().findAndRegisterModules()
    .configure(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES, true)
    .configure(DeserializationFeature.FAIL_ON_NULL_FOR_PRIMITIVES, true)
    .configure(DeserializationFeature.FAIL_ON_TRAILING_TOKENS, true)
    .configure(MapperFeature.ALLOW_COERCION_OF_SCALARS, false)

@Repository
class AiSettingsRepository(private val jdbc: JdbcClient) {
    fun preferences(actor: UUID): AiPreferences =
        jdbc.sql("SELECT settings::text FROM ai_user_preferences WHERE user_id=:id")
            .param("id", actor).query(String::class.java).optional().orElse(null)
            ?.let { aiJson.readValue(it, AiPreferences::class.java) } ?: AiPreferences()

    fun policy(owner: UUID): AiPolicy = jdbc.sql("SELECT settings::text FROM ai_workspace_policy WHERE owner_id=:id")
        .param("id", owner).query(String::class.java).optional().orElse(null)
        ?.let { aiJson.readValue(it, AiPolicy::class.java) } ?: AiPolicy()

    fun savePreferences(actor: UUID, value: AiPreferences) {
        jdbc.sql("INSERT INTO ai_user_preferences(user_id,settings) VALUES(:id,CAST(:settings AS jsonb)) ON CONFLICT(user_id) DO UPDATE SET settings=EXCLUDED.settings,updated_at=CURRENT_TIMESTAMP")
            .param("id", actor).param("settings", aiJson.writeValueAsString(value)).update()
    }

    fun savePolicy(owner: UUID, value: AiPolicy) {
        jdbc.sql("INSERT INTO ai_workspace_policy(owner_id,settings) VALUES(:id,CAST(:settings AS jsonb)) ON CONFLICT(owner_id) DO UPDATE SET settings=EXCLUDED.settings,updated_at=CURRENT_TIMESTAMP")
            .param("id", owner).param("settings", aiJson.writeValueAsString(value)).update()
    }
}

@Service
class AiSettingsService(
    val repository: AiSettingsRepository,
    private val rbac: RbacService,
    private val activity: ActivityService
) {
    fun preferences(actor: UUID): AiPreferences {
        rbac.require(actor, "conversations:read"); return repository.preferences(actor)
    }

    fun effectivePolicy(actor: UUID) = repository.policy(rbac.workspace(actor))
    fun policy(actor: UUID): AiPolicy {
        rbac.require(actor, "system_settings:read"); return effectivePolicy(actor)
    }

    @Transactional
    fun savePreferences(actor: UUID, value: AiPreferences): AiPreferences {
        rbac.authorizeMutation(actor, "conversations:update")
        if (value.allowedCloudProviders.any { it !in ModelRouter.providers - "ollama" } || value.allowedCloudProviders.distinct().size != value.allowedCloudProviders.size ||
            value.preferredProvider?.let { it !in ModelRouter.providers } == true || value.routingPreference !in setOf(
                "local_first",
                "economy"
            ) ||
            listOfNotNull(
                value.chatProfileId,
                value.voiceProfileId
            ).any { !validProfileId(it) } || value.monthlyTokenLimit?.let { it !in 1..1_000_000_000L } == true) throw AiFailure(
            "INVALID_REQUEST"
        )
        repository.savePreferences(actor, value)
        audit(actor, "ai.preferences.updated")
        return value
    }

    @Transactional
    fun savePolicy(actor: UUID, value: AiPolicy): AiPolicy {
        val owner = rbac.authorizeMutation(actor, "system_settings:update")
        if (value.allowedProviders.any { it !in ModelRouter.providers } || value.allowedProviders.distinct().size != value.allowedProviders.size ||
            value.cloudDataScope != "current_message" || value.taskProfiles.keys.any { it !in ModelRouter.tasks } ||
            (value.allowedProfiles + value.priorities + value.fallbackProfiles + value.taskProfiles.values.flatten()).let {
                it.size > 500 || it.any { id ->
                    !validProfileId(
                        id
                    )
                }
            } ||
            value.maxRequestTokens !in 256..1_000_000L || value.maxTimeoutSeconds !in 1..900 ||
            value.monthlyTokenLimit?.let { it !in 1..1_000_000_000L } == true ||
            value.monthlyCostLimit?.let {
                it.signum() < 0 || it > BigDecimal("1000000") || value.currency?.matches(
                    Regex(
                        "[A-Z]{3}"
                    )
                ) != true
            } == true) throw AiFailure("INVALID_REQUEST")
        repository.savePolicy(owner, value)
        audit(actor, "ai.policy.updated")
        return value
    }

    fun validateCloud(actor: UUID, provider: String) {
        val prefs = repository.preferences(actor)
        val policy = effectivePolicy(actor)
        if (prefs.localOnly || !policy.allowCloud || provider !in prefs.allowedCloudProviders || provider !in policy.allowedProviders) throw AiFailure(
            "CLOUD_NOT_ALLOWED",
            403
        )
    }

    private fun audit(actor: UUID, code: String) = activity.record(
        ActivityCategory.INTEGRATION, code, ActivityStatus.SUCCEEDED,
        ActivityActorType.USER, "kyrion-core", code, actor.toString(), ownerId = rbac.workspace(actor)
    )

    private fun validProfileId(id: String) = id.length in 1..128 && id.matches(Regex("[A-Za-z0-9_.:/-]+"))
}

data class AiUsageRow(
    val provider: String,
    val profileId: String,
    val modelId: String,
    val requests: Long,
    val chargedTokens: Long,
    val inputTokens: Long?,
    val outputTokens: Long?,
    val estimatedCost: BigDecimal?,
    val currency: String?,
    val pending: Long
)

data class AiUsageSummary(
    val period: String, val tokenLimit: Long?, val costLimit: BigDecimal?, val currency: String?,
    val chargedTokens: Long, val rows: List<AiUsageRow>, val costsAreEstimates: Boolean = true
)

data class AiReservation(
    val id: UUID,
    val tokens: Long,
    val inputEstimate: Long,
    val model: AiModel,
    val estimatedCost: BigDecimal?
)

fun effectiveTokenLimit(prefs: AiPreferences, policy: AiPolicy) =
    listOfNotNull(prefs.monthlyTokenLimit, policy.monthlyTokenLimit).minOrNull()

fun estimateAiCost(input: Long, output: Long, model: AiModel): BigDecimal? {
    val inputPrice = model.inputCostPerMillion ?: return null
    val outputPrice = model.outputCostPerMillion ?: return null
    return (inputPrice * BigDecimal(input) + outputPrice * BigDecimal(output)).divide(
        BigDecimal(1_000_000),
        8,
        RoundingMode.CEILING
    )
}

@Service
class AiUsageService(
    private val jdbc: JdbcClient, private val settings: AiSettingsService,
    private val rbac: RbacService, private val activity: ActivityService
) {
    fun period() = YearMonth.now(ZoneOffset.UTC).toString()
    fun summary(actor: UUID): AiUsageSummary {
        rbac.require(actor, "conversations:read")
        val rows = rows(actor, period())
        val prefs = settings.repository.preferences(actor)
        val policy = settings.effectivePolicy(actor)
        return AiUsageSummary(
            period(),
            effectiveTokenLimit(prefs, policy),
            policy.monthlyCostLimit,
            policy.currency,
            rows.sumOf { it.chargedTokens },
            rows
        )
    }

    private fun rows(actor: UUID, period: String) = jdbc.sql(
        """SELECT provider,profile_id,model_id,currency,COUNT(*) requests,SUM(charged_tokens) charged,
        SUM(reported_input_tokens) input,SUM(reported_output_tokens) output,SUM(estimated_cost) cost,
        COUNT(*) FILTER (WHERE state IN ('pending','uncertain')) pending FROM ai_usage_attempt WHERE actor_id=:actor AND period=:period
        GROUP BY provider,profile_id,model_id,currency ORDER BY provider,profile_id"""
    )
        .param("actor", actor).param("period", period).query { rs, _ ->
            AiUsageRow(
                rs.getString("provider"),
                rs.getString("profile_id"),
                rs.getString("model_id"),
                rs.getLong("requests"),
                rs.getLong("charged"),
                rs.getObject("input")?.let { rs.getLong("input") },
                rs.getObject("output")?.let { rs.getLong("output") },
                rs.getBigDecimal("cost"),
                rs.getString("currency"),
                rs.getLong("pending")
            )
        }.list()

    @Transactional
    fun reserve(
        actor: UUID,
        requestId: UUID,
        attempt: Int,
        model: AiModel,
        request: AiRouteRequest,
        catalog: AiCatalog,
        inputEstimate: Long
    ): AiReservation {
        rbac.authorizeMutation(actor, "conversations:create")
        // Same workspace lock as policy/permission mutations; no HTTP under this lock.
        jdbc.sql("SELECT id FROM user_account WHERE id=:id FOR UPDATE").param("id", actor).query(UUID::class.java)
            .single()
        val prefs = settings.repository.preferences(actor)
        val policy = settings.effectivePolicy(actor)
        val current = ModelRouter.select(catalog, prefs, policy, request)
        if ((attempt == 0 && current.model.id != model.id) || (attempt > 0 && model.id !in current.alternatives.map { it.id })) throw AiFailure(
            "ROUTE_CHANGED",
            409
        )
        val tokens = Math.addExact(inputEstimate, model.maxOutputTokens.toLong())
        if (tokens > policy.maxRequestTokens) throw AiFailure("REQUEST_BUDGET_EXCEEDED", 429)
        val rows = rows(actor, period())
        if (effectiveTokenLimit(
                prefs,
                policy
            )?.let { rows.sumOf { row -> row.chargedTokens } + tokens > it } == true
        ) throw AiFailure("TOKEN_BUDGET_EXCEEDED", 429)
        val cost = estimateAiCost(inputEstimate, model.maxOutputTokens.toLong(), model)
        if (policy.monthlyCostLimit != null) {
            if (cost == null || model.currency != policy.currency) throw AiFailure("COST_ESTIMATE_UNAVAILABLE", 403)
            if (rows.filter { it.currency == policy.currency }.sumOf {
                    it.estimatedCost ?: BigDecimal.ZERO
                } + cost > policy.monthlyCostLimit) throw AiFailure("COST_BUDGET_EXCEEDED", 429)
        }
        val id = UUID.randomUUID()
        val inserted = jdbc.sql(
            """INSERT INTO ai_usage_attempt(id,actor_id,request_id,attempt,provider,profile_id,model_id,period,charged_tokens,estimated_cost,currency)
            VALUES(:id,:actor,:request,:attempt,:provider,:profile,:model,:period,:tokens,:cost,:currency) ON CONFLICT(actor_id,request_id,attempt) DO NOTHING"""
        )
            .param("id", id).param("actor", actor).param("request", requestId).param("attempt", attempt)
            .param("provider", model.provider).param("profile", model.id)
            .param("model", model.modelId ?: model.id).param("period", period()).param("tokens", tokens)
            .param("cost", cost).param("currency", model.currency).update()
        if (inserted != 1) throw AiFailure("REQUEST_ALREADY_STARTED", 409)
        activity.record(
            ActivityCategory.INTEGRATION,
            "ai.usage.reserved",
            ActivityStatus.PROPOSED,
            ActivityActorType.USER,
            "kyrion-core",
            model.id,
            actor.toString(),
            requestId,
            actor
        )
        return AiReservation(id, tokens, inputEstimate, model, cost)
    }

    @Transactional
    fun settle(
        actor: UUID,
        reservation: AiReservation,
        input: Long?,
        output: Long?,
        total: Long?,
        completed: Boolean,
        error: String?
    ) {
        val reported = total ?: if (input != null && output != null) input + output else null
        val known = completed && reported != null
        val cost = if (known && input != null && output != null) estimateAiCost(
            input,
            output,
            reservation.model
        ) else reservation.estimatedCost
        jdbc.sql(
            """UPDATE ai_usage_attempt SET charged_tokens=:tokens,reported_input_tokens=:input,reported_output_tokens=:output,
            estimated_cost=:cost,state=:state,error_code=:error,settled_at=CURRENT_TIMESTAMP WHERE id=:id AND actor_id=:actor AND state='pending'"""
        )
            .param("id", reservation.id).param("actor", actor)
            .param("tokens", if (known) reported else reservation.tokens).param("input", input).param("output", output)
            .param("cost", cost).param("state", if (known) "reported" else if (completed) "estimated" else "uncertain")
            .param("error", error).update()
        activity.record(
            ActivityCategory.INTEGRATION,
            "ai.usage.settled",
            if (completed) ActivityStatus.SUCCEEDED else ActivityStatus.FAILED,
            ActivityActorType.USER,
            "kyrion-core",
            error ?: "ai.completed",
            actor.toString(),
            ownerId = actor
        )
    }
}
