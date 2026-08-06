package dev.kyrion.core.gateway

import com.fasterxml.jackson.databind.JsonNode
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

data class GatewayCommand(val id: UUID, val type: String, val payload: JsonNode)

@Repository
class GatewayCommandRepository(private val jdbc: JdbcClient) {
    private val mapper: ObjectMapper = jacksonObjectMapper()
    fun create(id: UUID, nodeId: UUID, ownerId: UUID, type: String, payload: Map<String, Any>, now: Instant) {
        jdbc.sql("""INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at)
            VALUES (:id,:nodeId,:ownerId,:type,CAST(:payload AS jsonb),'pending',:now)""")
            .param("id", id).param("nodeId", nodeId).param("ownerId", ownerId).param("type", type)
            .param("payload", mapper.writeValueAsString(payload)).param("now", Timestamp.from(now)).update()
    }

    @Transactional
    fun claim(nodeId: UUID, now: Instant): GatewayCommand? = jdbc.sql("""
        UPDATE gateway_command SET status='running', claimed_at=:now
        WHERE id=(SELECT id FROM gateway_command WHERE node_id=:nodeId AND status='pending'
          ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1)
        RETURNING id,command_type,payload""")
        .param("nodeId", nodeId).param("now", Timestamp.from(now))
        .query { rs, _ -> GatewayCommand(rs.getObject("id", UUID::class.java), rs.getString("command_type"), mapper.readTree(rs.getString("payload"))) }
        .optional().orElse(null)

    fun complete(id: UUID, nodeId: UUID, succeeded: Boolean, error: String?, now: Instant): Boolean =
        jdbc.sql("""UPDATE gateway_command SET status=:status,error_code=:error,completed_at=:now
            WHERE id=:id AND node_id=:nodeId AND status='running'""")
            .param("status", if (succeeded) "succeeded" else "failed").param("error", error)
            .param("now", Timestamp.from(now)).param("id", id).param("nodeId", nodeId).update() == 1
}

@Service
class GatewayCommandService(
    private val gateways: GatewayService,
    private val repository: GatewayCommandRepository,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun enqueue(ownerId: UUID, nodeId: UUID, type: String, payload: Map<String, Any>): UUID {
        val node = gateways.all(ownerId).singleOrNull { it.id == nodeId } ?: throw GatewayCommandInvalidException()
        if (node.availability == "offline") throw GatewayCommandUnavailableException()
        val id = UUID.randomUUID()
        repository.create(id, nodeId, ownerId, type, payload, clock.instant())
        activity.record(ActivityCategory.CAPABILITY, type, ActivityStatus.CONFIRMED, ActivityActorType.USER,
            "kyrion-core", type, nodeId.toString(), id)
        return id
    }

    fun next(nodeId: UUID, credential: String): GatewayCommand? {
        gateways.authenticate(nodeId, credential)
        return repository.claim(nodeId, clock.instant())
    }

    fun complete(nodeId: UUID, credential: String, id: UUID, succeeded: Boolean, error: String?) {
        val node = gateways.authenticate(nodeId, credential)
        if (!repository.complete(id, nodeId, succeeded, error?.take(80), clock.instant())) throw GatewayCommandInvalidException()
        activity.record(ActivityCategory.CAPABILITY, "gateway.command.completed",
            if (succeeded) ActivityStatus.SUCCEEDED else ActivityStatus.FAILED,
            ActivityActorType.INTEGRATION, "kyrion-gateway", error ?: "gateway.command.completed",
            node.ownerId.toString(), id)
    }
}

class GatewayCommandInvalidException : RuntimeException()
class GatewayCommandUnavailableException : RuntimeException()
