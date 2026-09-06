package dev.kyrion.core.gateway

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.util.UUID

data class GatewayCommand(val id: UUID, val type: String, val payload: Map<String, Any>)
data class GatewayCommandStatus(val id: UUID, val status: String, val errorCode: String?)

@Repository
class GatewayCommandRepository(private val jdbc: JdbcClient) {
    private val mapper: ObjectMapper = jacksonObjectMapper()
    fun create(id: UUID, nodeId: UUID, ownerId: UUID, type: String, payload: Map<String, Any>, now: Instant, correlationId: UUID = id) {
        jdbc.sql("""INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at,correlation_id)
            VALUES (:id,:nodeId,:ownerId,:type,CAST(:payload AS jsonb),'pending',:now,:correlation)""")
            .param("id", id).param("nodeId", nodeId).param("ownerId", ownerId).param("type", type)
            .param("payload", mapper.writeValueAsString(payload)).param("now", Timestamp.from(now)).param("correlation", correlationId).update()
    }

    fun correlation(ownerId: UUID, id: UUID): UUID = jdbc.sql("SELECT COALESCE(correlation_id,id) FROM gateway_command WHERE owner_id=:owner AND id=:id")
        .param("owner", ownerId).param("id", id).query(UUID::class.java).single()

    @Transactional
    fun claim(nodeId: UUID, now: Instant): GatewayCommand? = jdbc.sql("""
        UPDATE gateway_command SET status='running', claimed_at=:now
        WHERE id=(SELECT id FROM gateway_command WHERE node_id=:nodeId AND status='pending'
          ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
        RETURNING id,command_type,payload""")
        .param("nodeId", nodeId).param("now", Timestamp.from(now))
        .query { rs, _ ->
            @Suppress("UNCHECKED_CAST")
            val payload = mapper.readValue(rs.getString("payload"), Map::class.java) as Map<String, Any>
            GatewayCommand(rs.getObject("id", UUID::class.java), rs.getString("command_type"), payload)
        }
        .optional().orElse(null)

    fun complete(id: UUID, nodeId: UUID, succeeded: Boolean, error: String?, now: Instant): Boolean =
        jdbc.sql("""UPDATE gateway_command SET status=:status,error_code=:error,completed_at=:now
            WHERE id=:id AND node_id=:nodeId AND status='running'""")
            .param("status", if (succeeded) "succeeded" else "failed").param("error", error)
            .param("now", Timestamp.from(now)).param("id", id).param("nodeId", nodeId).update() == 1

    fun status(id: UUID): String? = jdbc.sql("SELECT status FROM gateway_command WHERE id=:id")
        .param("id", id).query(String::class.java).optional().orElse(null)

    fun status(ownerId: UUID, id: UUID): GatewayCommandStatus? = jdbc.sql(
        "SELECT id,status,error_code FROM gateway_command WHERE owner_id=:ownerId AND id=:id",
    ).param("ownerId", ownerId).param("id", id).query { rs, _ ->
        GatewayCommandStatus(rs.getObject("id", UUID::class.java), rs.getString("status"), rs.getString("error_code"))
    }.optional().orElse(null)
}

@Service
class GatewayCommandService(
    private val gateways: GatewayService,
    private val repository: GatewayCommandRepository,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun gateway(ownerId: UUID, nodeId: UUID) =
        gateways.all(ownerId).singleOrNull { it.id == nodeId } ?: throw GatewayCommandInvalidException()

    fun enqueue(ownerId: UUID, nodeId: UUID, type: String, payload: Map<String, Any>, correlationId: UUID? = null): UUID {
        val node = gateway(ownerId, nodeId)
        if (node.availability == "offline") throw GatewayCommandUnavailableException()
        val id = UUID.randomUUID()
        repository.create(id, nodeId, ownerId, type, payload, clock.instant(), correlationId ?: id)
        activity.record(ActivityCategory.CAPABILITY, type, ActivityStatus.CONFIRMED, ActivityActorType.USER,
            "kyrion-core", type, nodeId.toString(), id, ownerId)
        return id
    }

    fun enqueueAndAwait(ownerId: UUID, nodeId: UUID, type: String, payload: Map<String, Any>): Boolean {
        val id = enqueue(ownerId, nodeId, type, payload)
        repeat(48) {
            when (repository.status(id)) {
                "succeeded" -> return true
                "failed" -> return false
            }
            Thread.sleep(250)
        }
        return false
    }

    fun status(ownerId: UUID, id: UUID) = repository.status(ownerId, id) ?: throw GatewayCommandInvalidException()

    fun executeConfirmed(ownerId: UUID, nodeId: UUID, type: String, payload: Map<String, Any>, correlationId: UUID) {
        val id = enqueue(ownerId, nodeId, type, payload, correlationId)
        repeat(48) {
            val result = repository.status(ownerId, id) ?: throw GatewayExecutionException("adapter.invalid_result")
            when (result.status) {
                "succeeded" -> return
                "failed" -> throw GatewayExecutionException(gatewayDiagnosticCode(result.errorCode))
                "pending", "running" -> Unit
                else -> throw GatewayExecutionException("adapter.invalid_result")
            }
            Thread.sleep(250)
        }
        throw GatewayExecutionException("adapter.timeout")
    }

    fun next(nodeId: UUID, credential: String): GatewayCommand? {
        gateways.authenticate(nodeId, credential)
        return repository.claim(nodeId, clock.instant())
    }

    fun complete(nodeId: UUID, credential: String, id: UUID, succeeded: Boolean, error: String?) {
        val node = gateways.authenticate(nodeId, credential)
        if (!repository.complete(id, nodeId, succeeded, error?.take(80), clock.instant())) throw GatewayCommandInvalidException()
        activity.record(ActivityCategory.CAPABILITY, "action.adapter.completed",
            if (succeeded) ActivityStatus.SUCCEEDED else ActivityStatus.FAILED,
              ActivityActorType.INTEGRATION, "kyrion-gateway", if (succeeded) "action.succeeded" else gatewayDiagnosticCode(error),
              node.ownerId.toString(), repository.correlation(node.ownerId, id), node.ownerId)
    }
}

class GatewayCommandInvalidException : RuntimeException()
class GatewayCommandUnavailableException : RuntimeException()
class GatewayExecutionException(val code: String) : RuntimeException(code)

internal fun gatewayDiagnosticCode(code: String?): String = when (code) {
    "TIMEOUT", "COMMAND_TIMEOUT", "POWER_CONFIRMATION_TIMEOUT" -> "adapter.timeout"
    "INVALID_PAYLOAD", "INVALID_RESULT" -> "adapter.invalid_result"
    "DEVICE_OFFLINE", "DEVICE_UNAVAILABLE" -> "device.offline"
    else -> "adapter.failed"
}
