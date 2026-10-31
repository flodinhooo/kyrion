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
import java.time.Clock
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
    val pending: Long,
    val accountingState: String = "pending",
    val unknownCosts: Long = 0,
    val costBasis: String = "reservation"
)

data class AiOpenUsageAttempt(
    val id: UUID, val period: String, val provider: String, val profileId: String,
    val state: String, val chargedTokens: Long, val estimatedCost: BigDecimal?,
    val currency: String?, val errorCode: String?
)

data class AiUsageSummary(
    val period: String, val tokenLimit: Long?, val costLimit: BigDecimal?, val currency: String?,
    val chargedTokens: Long, val rows: List<AiUsageRow>, val costsAreEstimates: Boolean = true,
    val openAttempts: List<AiOpenUsageAttempt> = emptyList(), val openAttemptsTruncated: Boolean = false
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
    private val rbac: RbacService, private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC()
) {
    fun period() = YearMonth.now(clock.withZone(ZoneOffset.UTC)).toString()
    fun summary(actor: UUID): AiUsageSummary {
        rbac.require(actor, "conversations:read")
        val period = period()
        val rows = rows(actor, period)
        val prefs = settings.repository.preferences(actor)
        val policy = settings.effectivePolicy(actor)
        val open = jdbc.sql("""SELECT id,period,provider,profile_id,state,charged_tokens,estimated_cost,currency,error_code
            FROM ai_usage_attempt WHERE actor_id=:actor AND (state IN ('pending','invoked','uncertain','estimated')
                OR (state!='rejected' AND (estimated_cost IS NULL OR currency IS NULL)))
            ORDER BY created_at,id LIMIT 101""").param("actor", actor).query { rs, _ ->
            AiOpenUsageAttempt(rs.getObject("id", UUID::class.java), rs.getString("period"), rs.getString("provider"),
                rs.getString("profile_id"), rs.getString("state"), rs.getLong("charged_tokens"),
                rs.getBigDecimal("estimated_cost"), rs.getString("currency"), rs.getString("error_code"))
        }.list()
        return AiUsageSummary(
            period,
            effectiveTokenLimit(prefs, policy),
            policy.monthlyCostLimit,
            policy.currency,
            rows.sumOf { it.chargedTokens },
            rows, openAttempts = open.take(100), openAttemptsTruncated = open.size > 100
        )
    }

    private fun rows(actor: UUID, period: String) = jdbc.sql(
        """SELECT provider,profile_id,model_id,currency,COUNT(*) requests,SUM(charged_tokens) charged,
        CASE WHEN COUNT(*) FILTER (WHERE reported_input_tokens IS NULL)>0 THEN NULL ELSE SUM(reported_input_tokens) END input,
        CASE WHEN COUNT(*) FILTER (WHERE reported_output_tokens IS NULL)>0 THEN NULL ELSE SUM(reported_output_tokens) END output,
        CASE WHEN COUNT(*) FILTER (WHERE estimated_cost IS NULL OR currency IS NULL AND state!='rejected')>0 THEN NULL ELSE SUM(estimated_cost) END cost,
        COUNT(*) FILTER (WHERE estimated_cost IS NULL OR currency IS NULL AND state!='rejected') unknown_costs,state,
        CASE WHEN state='rejected' THEN 'not_invoked'
            WHEN state='reported' AND input_price IS NOT NULL AND output_price IS NOT NULL
                AND reported_total_tokens=reported_input_tokens+reported_output_tokens THEN 'provider_usage_estimate'
            ELSE 'reservation' END cost_basis,
        COUNT(*) FILTER (WHERE state IN ('pending','invoked','uncertain','estimated')) pending FROM ai_usage_attempt WHERE actor_id=:actor AND period=:period
        GROUP BY provider,profile_id,model_id,currency,state,cost_basis ORDER BY provider,profile_id,state,cost_basis"""
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
                rs.getLong("pending"), rs.getString("state"), rs.getLong("unknown_costs"), rs.getString("cost_basis")
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
        // Capture after acquiring the account lock; budget checks and insertion
        // must use the same UTC month even when this request crosses midnight.
        val period = period()
        val rows = rows(actor, period)
        if (effectiveTokenLimit(
                prefs,
                policy
            )?.let { rows.sumOf { row -> row.chargedTokens } + tokens > it } == true
        ) throw AiFailure("TOKEN_BUDGET_EXCEEDED", 429)
        val cost = estimateAiCost(inputEstimate, model.maxOutputTokens.toLong(), model)
        if (policy.monthlyCostLimit != null) {
            if (cost == null || model.currency != policy.currency) throw AiFailure("COST_ESTIMATE_UNAVAILABLE", 403)
            if (rows.any { it.accountingState != "rejected" && (it.unknownCosts > 0 || it.estimatedCost == null || it.currency != policy.currency) })
                throw AiFailure("COST_ESTIMATE_UNAVAILABLE", 403)
            if (rows.sumOf {
                    it.estimatedCost ?: BigDecimal.ZERO // Rejected attempts have a proven zero charge.
                } + cost > policy.monthlyCostLimit) throw AiFailure("COST_BUDGET_EXCEEDED", 429)
        }
        val id = UUID.randomUUID()
        val inserted = jdbc.sql(
            """INSERT INTO ai_usage_attempt(id,actor_id,request_id,attempt,provider,profile_id,model_id,period,charged_tokens,estimated_cost,currency,
            reserved_tokens,reserved_cost,input_price,output_price)
            VALUES(:id,:actor,:request,:attempt,:provider,:profile,:model,:period,:tokens,:cost,:currency,:tokens,:cost,:inputPrice,:outputPrice)
            ON CONFLICT(actor_id,request_id,attempt) DO NOTHING"""
        )
            .param("id", id).param("actor", actor).param("request", requestId).param("attempt", attempt)
            .param("provider", model.provider).param("profile", model.id)
            .param("model", model.modelId ?: model.id).param("period", period).param("tokens", tokens)
            .param("cost", cost).param("currency", model.currency)
            .param("inputPrice", model.inputCostPerMillion).param("outputPrice", model.outputCostPerMillion).update()
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

    /** Commit before network I/O. The same prepared generation cannot invoke twice. */
    @Transactional
    fun begin(actor: UUID, reservation: AiReservation) {
        rbac.authorizeMutation(actor, "conversations:create")
        val updated = jdbc.sql("""UPDATE ai_usage_attempt SET state='invoked',invoked_at=CURRENT_TIMESTAMP
            WHERE id=:id AND actor_id=:actor AND state='pending'""")
            .param("id", reservation.id).param("actor", actor).update()
        if (updated != 1) throw AiFailure("REQUEST_ALREADY_STARTED", 409)
        auditTransition(actor, reservation.id, "ai.usage.invoked", ActivityStatus.PROPOSED, "ai.usage.invoked")
    }

    @Transactional
    fun releaseUninvoked(actor: UUID, reservation: AiReservation, error: String) {
        val updated = jdbc.sql("UPDATE ai_usage_attempt SET charged_tokens=0,estimated_cost=0,state='rejected',error_code=:error,settled_at=CURRENT_TIMESTAMP WHERE id=:id AND actor_id=:actor AND state='pending'")
            .param("id",reservation.id).param("actor",actor).param("error",error).update()
        if (updated == 0) return
        auditTransition(actor, reservation.id, "ai.usage.rejected", ActivityStatus.DENIED, error)
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
        // The existing account lock serializes reconciliation with budget checks.
        jdbc.sql("SELECT id FROM user_account WHERE id=:id FOR UPDATE").param("id", actor)
            .query(UUID::class.java).optional()
        val valid = validAiUsage(input, output, total)
        val terminal = completed && error == null
        val reported = total ?: if (input != null && output != null && valid) input + output else null
        val known = terminal && valid && input != null && output != null && reported != null
        val priced = valid && input != null && output != null && input + output == reported
        val unpricedCategories = valid && input != null && output != null && reported != null && reported > input + output
        val updated = jdbc.sql(
            """UPDATE ai_usage_attempt SET charged_tokens=CASE WHEN :known THEN :tokens ELSE GREATEST(reserved_tokens,:tokens) END,
            reported_input_tokens=:input,reported_output_tokens=:output,
            reported_total_tokens=:total,
            estimated_cost=CASE WHEN :unpricedCategories THEN NULL
                WHEN :priced AND input_price IS NOT NULL AND output_price IS NOT NULL
                THEN CASE WHEN :known THEN CEIL((input_price*:input+output_price*:output)*100)/100000000
                    ELSE GREATEST(reserved_cost,CEIL((input_price*:input+output_price*:output)*100)/100000000) END
                ELSE reserved_cost END,
            state=:state,error_code=:error,settled_at=CURRENT_TIMESTAMP WHERE id=:id AND actor_id=:actor
            AND (state IN ('pending','invoked') OR (:known AND state IN ('uncertain','estimated')
                AND error_code IS DISTINCT FROM 'USAGE_CONFLICT'))"""
        )
            .param("id", reservation.id).param("actor", actor)
            .param("tokens", reported?.takeIf { valid } ?: 0L).param("input", input?.takeIf { valid }).param("output", output?.takeIf { valid })
            .param("total", reported?.takeIf { valid }).param("known", known).param("priced", priced)
            .param("unpricedCategories", unpricedCategories)
            .param("state", if (known) "reported" else if (terminal && valid) "estimated" else "uncertain")
            .param("error", if (!valid) "USAGE_INVALID" else error).update()
        if (updated == 0) {
            if (known) {
                val disputed = jdbc.sql("""UPDATE ai_usage_attempt SET state='uncertain',error_code='USAGE_CONFLICT',
                    charged_tokens=GREATEST(charged_tokens,reserved_tokens,:tokens),estimated_cost=NULL
                    WHERE id=:id AND actor_id=:actor AND state='reported'
                    AND (reported_input_tokens IS DISTINCT FROM :input OR reported_output_tokens IS DISTINCT FROM :output
                        OR COALESCE(reported_total_tokens,reported_input_tokens+reported_output_tokens) IS DISTINCT FROM :total)""")
                    .param("id", reservation.id).param("actor", actor).param("tokens", reported)
                    .param("input", input).param("output", output).param("total", reported).update()
                if (disputed == 1) auditTransition(actor, reservation.id, "ai.usage.disputed", ActivityStatus.FAILED, "USAGE_CONFLICT")
            }
            return
        }
        auditTransition(actor, reservation.id, "ai.usage.settled",
            if (terminal && valid) ActivityStatus.SUCCEEDED else ActivityStatus.FAILED,
            if (!valid) "USAGE_INVALID" else error ?: "ai.completed")
    }

    private fun auditTransition(actor: UUID, id: UUID, event: String, status: ActivityStatus, code: String) {
        val request = jdbc.sql("SELECT request_id FROM ai_usage_attempt WHERE id=:id AND actor_id=:actor")
            .param("id", id).param("actor", actor).query(UUID::class.java).single()
        activity.record(
            ActivityCategory.INTEGRATION, event, status, ActivityActorType.USER,
            "kyrion-core", code, actor.toString(), request, actor
        )
    }
}

internal fun validAiUsage(input: Long?, output: Long?, total: Long?): Boolean =
    listOfNotNull(input, output, total).all { it in 0..1_000_000_000L } &&
        (total == null || total >= (input ?: 0) + (output ?: 0))
