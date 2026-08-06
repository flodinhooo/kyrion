package dev.kyrion.core.gateway

import com.fasterxml.jackson.databind.ObjectMapper
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.security.SessionTokenService
import org.springframework.dao.DuplicateKeyException
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.sql.Timestamp
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.util.UUID

data class GatewayEnrollment(
    val id: UUID,
    val ownerId: UUID,
    val tokenHash: String,
    val displayName: String,
    val expiresAt: Instant,
    val usedAt: Instant?,
    val createdAt: Instant,
)

data class GatewayNode(
    val id: UUID,
    val ownerId: UUID,
    val displayName: String,
    val hostname: String,
    val credentialHash: String,
    val agentVersion: String,
    val osName: String,
    val osVersion: String,
    val architecture: String,
    val lastSeenAt: Instant?,
    val health: GatewayHealth?,
    val createdAt: Instant,
    val updatedAt: Instant,
)

data class GatewayHealth(
    val temperatureCelsius: Double?,
    val throttled: Boolean,
    val memoryTotalBytes: Long,
    val memoryAvailableBytes: Long,
    val storageTotalBytes: Long,
    val storageAvailableBytes: Long,
    val ethernet: GatewayInterfaceHealth,
    val wifi: GatewayInterfaceHealth,
    val ipv6: Boolean,
    val bluetooth: Boolean,
    val systemState: String,
    val adapters: List<GatewayAdapterHealth>,
    val zigbee: GatewayZigbeeHealth?,
    val services: List<GatewayServiceHealth>,
)

data class GatewayInterfaceHealth(val present: Boolean, val connected: Boolean)
data class GatewayAdapterHealth(
    val id: String,
    val protocol: String,
    val vendor: String,
    val model: String,
    val serial: String,
    val path: String,
)
data class GatewayZigbeeHealth(
    val permitJoin: Boolean,
    val channel: Int,
    val devices: List<GatewayZigbeeDevice>,
)
data class GatewayZigbeeDevice(
    val ieeeAddress: String,
    val friendlyName: String,
    val vendor: String,
    val model: String,
    val description: String,
    val supported: Boolean,
    val on: Boolean?,
    val brightness: Int?,
    val linkquality: Int?,
)
data class GatewayServiceHealth(val id: String, val status: String)

interface GatewayRepository {
    fun createEnrollment(enrollment: GatewayEnrollment)
    fun consumeEnrollment(tokenHash: String, usedAt: Instant): GatewayEnrollment?
    fun create(node: GatewayNode)
    fun all(ownerId: UUID): List<GatewayNode>
    fun findById(id: UUID): GatewayNode?
    fun updateHeartbeat(id: UUID, credentialHash: String, health: GatewayHealth, seenAt: Instant): Boolean
}

@Repository
class JdbcGatewayRepository(
    private val jdbc: JdbcClient,
) : GatewayRepository {
    private val objectMapper: ObjectMapper = jacksonObjectMapper()
    override fun createEnrollment(enrollment: GatewayEnrollment) {
        jdbc.sql(
            """INSERT INTO gateway_enrollment
               (id, owner_id, token_hash, display_name, expires_at, used_at, created_at)
               VALUES (:id, :ownerId, :tokenHash, :displayName, :expiresAt, NULL, :createdAt)""",
        ).param("id", enrollment.id).param("ownerId", enrollment.ownerId)
            .param("tokenHash", enrollment.tokenHash).param("displayName", enrollment.displayName)
            .param("expiresAt", Timestamp.from(enrollment.expiresAt))
            .param("createdAt", Timestamp.from(enrollment.createdAt)).update()
    }

    override fun consumeEnrollment(tokenHash: String, usedAt: Instant): GatewayEnrollment? = jdbc.sql(
        """UPDATE gateway_enrollment SET used_at = :usedAt
           WHERE token_hash = :tokenHash AND used_at IS NULL AND expires_at > :usedAt
           RETURNING *""",
    ).param("usedAt", Timestamp.from(usedAt)).param("tokenHash", tokenHash)
        .query { rs, _ ->
            GatewayEnrollment(
                rs.getObject("id", UUID::class.java), rs.getObject("owner_id", UUID::class.java),
                rs.getString("token_hash"), rs.getString("display_name"),
                rs.getTimestamp("expires_at").toInstant(), rs.getTimestamp("used_at")?.toInstant(),
                rs.getTimestamp("created_at").toInstant(),
            )
        }.optional().orElse(null)

    override fun create(node: GatewayNode) {
        try {
            jdbc.sql(
                """INSERT INTO gateway_node
                   (id, owner_id, display_name, hostname, credential_hash, agent_version, os_name,
                    os_version, architecture, last_seen_at, health, created_at, updated_at)
                   VALUES (:id, :ownerId, :displayName, :hostname, :credentialHash, :agentVersion,
                    :osName, :osVersion, :architecture, NULL, NULL, :createdAt, :updatedAt)""",
            ).param("id", node.id).param("ownerId", node.ownerId).param("displayName", node.displayName)
                .param("hostname", node.hostname).param("credentialHash", node.credentialHash)
                .param("agentVersion", node.agentVersion).param("osName", node.osName)
                .param("osVersion", node.osVersion).param("architecture", node.architecture)
                .param("createdAt", Timestamp.from(node.createdAt)).param("updatedAt", Timestamp.from(node.updatedAt))
                .update()
        } catch (_: DuplicateKeyException) {
            throw GatewayAlreadyRegisteredException()
        }
    }

    override fun all(ownerId: UUID): List<GatewayNode> = jdbc.sql(
        "SELECT * FROM gateway_node WHERE owner_id = :ownerId ORDER BY lower(display_name)",
    ).param("ownerId", ownerId).query { rs, _ -> mapNode(rs) }.list()

    override fun findById(id: UUID): GatewayNode? = jdbc.sql("SELECT * FROM gateway_node WHERE id = :id")
        .param("id", id).query { rs, _ -> mapNode(rs) }.optional().orElse(null)

    override fun updateHeartbeat(id: UUID, credentialHash: String, health: GatewayHealth, seenAt: Instant): Boolean =
        jdbc.sql(
            """UPDATE gateway_node SET health = CAST(:health AS jsonb), last_seen_at = :seenAt,
               updated_at = :seenAt WHERE id = :id AND credential_hash = :credentialHash""",
        ).param("health", objectMapper.writeValueAsString(health)).param("seenAt", Timestamp.from(seenAt))
            .param("id", id).param("credentialHash", credentialHash).update() == 1

    private fun mapNode(rs: java.sql.ResultSet): GatewayNode {
        val healthJson = rs.getString("health")
        return GatewayNode(
            rs.getObject("id", UUID::class.java), rs.getObject("owner_id", UUID::class.java),
            rs.getString("display_name"), rs.getString("hostname"), rs.getString("credential_hash"),
            rs.getString("agent_version"), rs.getString("os_name"), rs.getString("os_version"),
            rs.getString("architecture"), rs.getTimestamp("last_seen_at")?.toInstant(),
            healthJson?.let { objectMapper.readValue(it, GatewayHealth::class.java) },
            rs.getTimestamp("created_at").toInstant(), rs.getTimestamp("updated_at").toInstant(),
        )
    }
}

data class CreatedGatewayEnrollment(val id: UUID, val enrollmentToken: String, val expiresAt: Instant)
data class RegisteredGateway(val node: GatewayNode, val gatewayToken: String)

@Service
class GatewayService(
    private val repository: GatewayRepository,
    private val tokens: SessionTokenService,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun createEnrollment(ownerId: UUID, displayName: String): CreatedGatewayEnrollment {
        val now = clock.instant()
        val token = tokens.create()
        val enrollment = GatewayEnrollment(
            UUID.randomUUID(), ownerId, token.tokenHash, displayName, now.plus(ENROLLMENT_TTL), null, now,
        )
        repository.createEnrollment(enrollment)
        activity.record(
            ActivityCategory.SECURITY, "gateway.enrollment.created", ActivityStatus.SUCCEEDED,
            ActivityActorType.USER, "kyrion-core", "gateway.enrollment.created", ownerId.toString(), enrollment.id,
        )
        return CreatedGatewayEnrollment(enrollment.id, token.rawToken, enrollment.expiresAt)
    }

    @Transactional
    fun enroll(token: String, hostname: String, agentVersion: String, osName: String, osVersion: String, architecture: String): RegisteredGateway {
        val now = clock.instant()
        val enrollment = repository.consumeEnrollment(tokens.hash(token), now) ?: throw GatewayEnrollmentInvalidException()
        val credential = tokens.create()
        val node = GatewayNode(
            UUID.randomUUID(), enrollment.ownerId, enrollment.displayName, hostname, credential.tokenHash,
            agentVersion, osName, osVersion, architecture, null, null, now, now,
        )
        repository.create(node)
        activity.record(
            ActivityCategory.SECURITY, "gateway.registered", ActivityStatus.SUCCEEDED,
            ActivityActorType.INTEGRATION, "kyrion-gateway", "gateway.registered", node.id.toString(), enrollment.id,
        )
        return RegisteredGateway(node, credential.rawToken)
    }

    fun all(ownerId: UUID): List<GatewayNodeView> = repository.all(ownerId).map { it.view(clock.instant()) }

    fun heartbeat(nodeId: UUID, rawCredential: String, health: GatewayHealth) {
        validateHealth(health)
        if (!repository.updateHeartbeat(nodeId, tokens.hash(rawCredential), health, clock.instant())) {
            throw GatewayUnauthenticatedException()
        }
    }

    fun authenticate(nodeId: UUID, rawCredential: String): GatewayNode =
        repository.findById(nodeId)?.takeIf { it.credentialHash == tokens.hash(rawCredential) }
            ?: throw GatewayUnauthenticatedException()

    private fun validateHealth(health: GatewayHealth) {
        if (health.temperatureCelsius != null && health.temperatureCelsius !in -20.0..150.0) {
            throw GatewayHealthInvalidException()
        }
        if (health.memoryTotalBytes <= 0 || health.memoryAvailableBytes !in 0..health.memoryTotalBytes) {
            throw GatewayHealthInvalidException()
        }
        if (health.storageTotalBytes <= 0 || health.storageAvailableBytes !in 0..health.storageTotalBytes) {
            throw GatewayHealthInvalidException()
        }
        if (health.systemState !in setOf("running", "degraded", "maintenance", "unknown")) {
            throw GatewayHealthInvalidException()
        }
        if (health.adapters.size > 16 || health.adapters.any {
                it.id.length !in 1..200 || it.protocol !in setOf("zigbee", "thread") ||
                    it.vendor.length !in 1..100 || it.model.length !in 1..160 ||
                    it.serial.length !in 1..160 || it.path.length !in 1..300 ||
                    !it.path.startsWith("/dev/serial/by-id/")
            }
        ) throw GatewayHealthInvalidException()
        if (health.zigbee != null && (health.zigbee.channel !in 11..26 ||
                health.zigbee.devices.size > 100 || health.zigbee.devices.any {
                    !it.ieeeAddress.matches(Regex("^0x[0-9a-f]{16}$")) ||
                        it.friendlyName.length !in 1..160 || it.vendor.length !in 1..100 ||
                        it.model.length !in 1..100 || it.description.length !in 1..200 ||
                        (it.brightness != null && it.brightness !in 0..254) ||
                        (it.linkquality != null && it.linkquality !in 0..255)
                })) throw GatewayHealthInvalidException()
        if (health.services.size > 32 || health.services.any {
                it.id.length !in 1..80 || !it.id.matches(Regex("^[a-z0-9.-]+$")) ||
                    it.status !in setOf("ready", "unavailable", "not_configured", "degraded", "unknown")
            }
        ) throw GatewayHealthInvalidException()
    }

    private fun GatewayNode.view(now: Instant): GatewayNodeView {
        val availability = when {
            lastSeenAt == null -> "unknown"
            Duration.between(lastSeenAt, now) > HEARTBEAT_STALE_AFTER -> "offline"
            health?.systemState == "degraded" -> "degraded"
            else -> "online"
        }
        return GatewayNodeView(
            id, displayName, hostname, availability, agentVersion, osName, osVersion, architecture,
            lastSeenAt, health, createdAt,
        )
    }

    companion object {
        val ENROLLMENT_TTL: Duration = Duration.ofMinutes(10)
        val HEARTBEAT_STALE_AFTER: Duration = Duration.ofSeconds(45)
    }
}

data class GatewayNodeView(
    val id: UUID,
    val displayName: String,
    val hostname: String,
    val availability: String,
    val agentVersion: String,
    val osName: String,
    val osVersion: String,
    val architecture: String,
    val lastSeenAt: Instant?,
    val health: GatewayHealth?,
    val createdAt: Instant,
)

class GatewayEnrollmentInvalidException : RuntimeException()
class GatewayAlreadyRegisteredException : RuntimeException()
class GatewayUnauthenticatedException : RuntimeException()
class GatewayHealthInvalidException : RuntimeException()
