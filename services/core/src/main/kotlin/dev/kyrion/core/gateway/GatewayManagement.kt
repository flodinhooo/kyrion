package dev.kyrion.core.gateway

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.security.authenticatedUserId
import dev.kyrion.core.security.workspaceOwnerId
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Pattern
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PutMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.bind.annotation.RestControllerAdvice
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.util.UUID

data class ManagedGateway(
    val id: UUID,
    val displayName: String,
    val hostname: String,
    val osName: String,
    val architecture: String,
    val agentVersion: String,
    val expectedAvailability: String,
    val revision: UUID,
    val lastSeenAt: Instant?,
    val revokedAt: Instant?,
    val allowedTasks: List<String>?,
    val availability: String = "unknown",
    val reportedServices: List<GatewayServiceHealth> = emptyList(),
)

data class UpdateGatewayManagementRequest(
    val revision: UUID,
    @field:NotBlank @field:Size(max = 120) val displayName: String,
    @field:Pattern(regexp = "^(unknown|always_on|intermittent)$") val expectedAvailability: String,
)

data class RevokeGatewayRequest(val revision: UUID)
data class UpdateGatewayTasksRequest(val revision: UUID, @field:Size(max = 2) val allowedTasks: List<String>)

@Service
class GatewayManagementService(
    private val jdbc: JdbcClient,
    private val activity: ActivityService,
    private val gateways: GatewayService,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val mapper = jacksonObjectMapper()

    fun all(ownerId: UUID): List<ManagedGateway> {
        val observations = gateways.all(ownerId).associateBy { it.id }
        return jdbc.sql("SELECT * FROM gateway_node WHERE owner_id=:owner ORDER BY lower(display_name),id")
            .param("owner", ownerId).query { rs, _ -> map(rs) }.list().map { node ->
                val observed = observations[node.id]
                node.copy(availability = if (node.revokedAt != null) "revoked" else observed?.availability ?: "unknown",
                    reportedServices = observed?.health?.services.orEmpty())
            }
    }

    private fun locked(ownerId: UUID, id: UUID): ManagedGateway = jdbc.sql(
        "SELECT * FROM gateway_node WHERE owner_id=:owner AND id=:id FOR UPDATE",
    ).param("owner", ownerId).param("id", id).query { rs, _ -> map(rs) }
        .optional().orElse(null) ?: throw GatewayManagementNotFoundException()

    @Transactional
    fun update(ownerId: UUID, actorId: UUID, id: UUID, request: UpdateGatewayManagementRequest): ManagedGateway {
        val name = request.displayName.trim()
        if (name.isEmpty() || name.length > 120 || name.any { Character.isISOControl(it) } ||
            request.expectedAvailability !in setOf("unknown", "always_on", "intermittent")
        ) throw GatewayManagementInvalidException()
        val current = locked(ownerId, id)
        if (current.revokedAt != null || current.revision != request.revision) throw GatewayManagementConflictException()
        // An acknowledged retry is a no-op and produces no duplicate audit event.
        if (current.displayName == name && current.expectedAvailability == request.expectedAvailability) return current
        val revision = UUID.randomUUID()
        jdbc.sql("""UPDATE gateway_node SET display_name=:name,expected_availability=:availability,
            management_revision=:revision,updated_at=:now WHERE id=:id AND owner_id=:owner""")
            .param("name", name).param("availability", request.expectedAvailability).param("revision", revision)
            .param("now", Timestamp.from(clock.instant())).param("id", id).param("owner", ownerId).update()
        audit(ownerId, actorId, id, "gateway.management.updated")
        return locked(ownerId, id)
    }

    @Transactional
    fun revoke(ownerId: UUID, actorId: UUID, id: UUID, revision: UUID): ManagedGateway {
        val current = locked(ownerId, id)
        if (current.revokedAt != null) return current
        if (current.revision != revision) throw GatewayManagementConflictException()
        val now = Timestamp.from(clock.instant())
        jdbc.sql("""UPDATE gateway_node SET revoked_at=:now,updated_at=:now,
            management_revision=:revision,credential_hash=:invalid WHERE id=:id AND owner_id=:owner""")
            .param("now", now).param("revision", UUID.randomUUID()).param("invalid", "revoked:" + UUID.randomUUID())
            .param("id", id).param("owner", ownerId).update()
        jdbc.sql("""UPDATE gateway_command SET status='failed',error_code='gateway.revoked',completed_at=:now
            WHERE node_id=:id AND owner_id=:owner AND status IN ('pending','running')""")
            .param("now", now).param("id", id).param("owner", ownerId).update()
        jdbc.sql("""UPDATE voice_satellite SET revoked_at=:now,updated_at=:now,
            credential_hash='revoked:'||gen_random_uuid()::text
            WHERE source_gateway_node_id=:id AND owner_id=:owner AND revoked_at IS NULL""")
            .param("now", now).param("id", id).param("owner", ownerId).update()
        jdbc.sql("""UPDATE voice_dialogue_session SET status='closed',close_reason='interrupted',closed_at=:now
            WHERE owner_id=:owner AND status='active' AND satellite_id IN
            (SELECT id FROM voice_satellite WHERE source_gateway_node_id=:id AND owner_id=:owner)""")
            .param("now", now).param("owner", ownerId).param("id", id).update()
        audit(ownerId, actorId, id, "gateway.revoked")
        return locked(ownerId, id)
    }

    @Transactional
    fun tasks(ownerId: UUID, actorId: UUID, id: UUID, request: UpdateGatewayTasksRequest): ManagedGateway {
        if (request.allowedTasks.size > 2 || request.allowedTasks.distinct().size != request.allowedTasks.size ||
            request.allowedTasks.any { it !in setOf("integration", "voice") }
        ) throw GatewayManagementInvalidException()
        val current = locked(ownerId, id)
        if (current.revokedAt != null || current.revision != request.revision) throw GatewayManagementConflictException()
        val selected = request.allowedTasks.sorted()
        if (current.allowedTasks == selected) return current
        val now = Timestamp.from(clock.instant())
        jdbc.sql("""UPDATE gateway_node SET task_policy=CAST(:tasks AS jsonb),management_revision=:revision,
            updated_at=:now WHERE id=:id AND owner_id=:owner""")
            .param("tasks", mapper.writeValueAsString(selected)).param("revision", UUID.randomUUID())
            .param("now", now).param("id", id).param("owner", ownerId).update()
        if ("integration" !in selected) {
            jdbc.sql("""UPDATE gateway_command SET status='failed',error_code='gateway.task_revoked',completed_at=:now
                WHERE node_id=:id AND owner_id=:owner AND status IN ('pending','running')""")
                .param("now", now).param("id", id).param("owner", ownerId).update()
        }
        if ("voice" !in selected) {
            jdbc.sql("""UPDATE voice_dialogue_session SET status='closed',close_reason='interrupted',closed_at=:now
                WHERE owner_id=:owner AND status='active' AND satellite_id IN
                (SELECT id FROM voice_satellite WHERE source_gateway_node_id=:id AND owner_id=:owner)""")
                .param("now", now).param("owner", ownerId).param("id", id).update()
        }
        audit(ownerId, actorId, id, "gateway.tasks.updated")
        return locked(ownerId, id)
    }

    private fun audit(ownerId: UUID, actorId: UUID, id: UUID, event: String) {
        activity.record(ActivityCategory.SECURITY, event, ActivityStatus.SUCCEEDED,
            ActivityActorType.USER, "kyrion-core", event, actorId.toString(), id, ownerId)
    }

    private fun map(rs: java.sql.ResultSet) = ManagedGateway(
        rs.getObject("id", UUID::class.java), rs.getString("display_name"), rs.getString("hostname"),
        rs.getString("os_name"), rs.getString("architecture"), rs.getString("agent_version"),
        rs.getString("expected_availability"), rs.getObject("management_revision", UUID::class.java),
        rs.getTimestamp("last_seen_at")?.toInstant(), rs.getTimestamp("revoked_at")?.toInstant(),
        rs.getString("task_policy")?.let { mapper.readTree(it).map { item -> item.asText() } },
    )
}

@RestController
@RequestMapping("/v1/gateways")
class GatewayManagementController(private val service: GatewayManagementService) {
    @GetMapping("/management")
    fun all(request: HttpServletRequest) = service.all(request.workspaceOwnerId())

    @PutMapping("/{id}/management")
    fun update(@PathVariable id: UUID, @Valid @RequestBody body: UpdateGatewayManagementRequest, request: HttpServletRequest) =
        service.update(request.workspaceOwnerId(), request.authenticatedUserId(), id, body)

    @DeleteMapping("/{id}")
    fun revoke(@PathVariable id: UUID, @RequestBody body: RevokeGatewayRequest, request: HttpServletRequest) =
        service.revoke(request.workspaceOwnerId(), request.authenticatedUserId(), id, body.revision)

    @PutMapping("/{id}/tasks")
    fun tasks(@PathVariable id: UUID, @Valid @RequestBody body: UpdateGatewayTasksRequest, request: HttpServletRequest) =
        service.tasks(request.workspaceOwnerId(), request.authenticatedUserId(), id, body)
}

class GatewayManagementNotFoundException : RuntimeException()
class GatewayManagementConflictException : RuntimeException()
class GatewayManagementInvalidException : RuntimeException()

@RestControllerAdvice(assignableTypes = [GatewayManagementController::class])
class GatewayManagementAdvice {
    @ExceptionHandler(GatewayManagementNotFoundException::class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    fun missing() = mapOf("code" to "gateway_not_found")

    @ExceptionHandler(GatewayManagementConflictException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun conflict() = mapOf("code" to "gateway_management_conflict")

    @ExceptionHandler(GatewayManagementInvalidException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = mapOf("code" to "gateway_management_invalid")
}
