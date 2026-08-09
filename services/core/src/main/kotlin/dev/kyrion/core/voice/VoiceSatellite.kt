package dev.kyrion.core.voice

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.security.SessionTokenService
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import java.sql.Timestamp
import java.time.Clock
import java.time.Duration
import java.time.Instant
import java.util.UUID

data class VoiceSatelliteEnrollment(
    val id: UUID,
    val ownerId: UUID,
    val tokenHash: String,
    val displayName: String,
    val expiresAt: Instant,
    val usedAt: Instant?,
    val createdAt: Instant,
)

data class VoiceSatellite(
    val id: UUID,
    val ownerId: UUID,
    val displayName: String,
    val hostname: String,
    val credentialHash: String,
    val runtimeVersion: String,
    val createdAt: Instant,
    val updatedAt: Instant,
)

data class VoiceDialogueSession(
    val id: UUID,
    val satelliteId: UUID,
    val ownerId: UUID,
    val conversationId: UUID,
    val status: String,
    val closeReason: String?,
    val startedAt: Instant,
    val lastActivityAt: Instant,
    val expiresAt: Instant,
    val closedAt: Instant?,
)

interface VoiceSatelliteRepository {
    fun createEnrollment(enrollment: VoiceSatelliteEnrollment)
    fun consumeEnrollment(tokenHash: String, usedAt: Instant): VoiceSatelliteEnrollment?
    fun createSatellite(satellite: VoiceSatellite)
    fun findSatellite(id: UUID): VoiceSatellite?
    fun createSession(session: VoiceDialogueSession)
    fun findSession(id: UUID, satelliteId: UUID): VoiceDialogueSession?
    fun closeSession(id: UUID, satelliteId: UUID, reason: String, closedAt: Instant): Boolean
}

@Repository
class JdbcVoiceSatelliteRepository(private val jdbc: JdbcClient) : VoiceSatelliteRepository {
    override fun createEnrollment(enrollment: VoiceSatelliteEnrollment) {
        jdbc.sql(
            """INSERT INTO voice_satellite_enrollment
               (id, owner_id, token_hash, display_name, expires_at, used_at, created_at)
               VALUES (:id, :ownerId, :tokenHash, :displayName, :expiresAt, NULL, :createdAt)""",
        ).param("id", enrollment.id).param("ownerId", enrollment.ownerId)
            .param("tokenHash", enrollment.tokenHash).param("displayName", enrollment.displayName)
            .param("expiresAt", Timestamp.from(enrollment.expiresAt))
            .param("createdAt", Timestamp.from(enrollment.createdAt)).update()
    }

    override fun consumeEnrollment(tokenHash: String, usedAt: Instant): VoiceSatelliteEnrollment? =
        jdbc.sql(
            """UPDATE voice_satellite_enrollment SET used_at = :usedAt
               WHERE token_hash = :tokenHash AND used_at IS NULL AND expires_at > :usedAt
               RETURNING *""",
        ).param("tokenHash", tokenHash).param("usedAt", Timestamp.from(usedAt)).query { rs, _ ->
            VoiceSatelliteEnrollment(
                rs.getObject("id", UUID::class.java), rs.getObject("owner_id", UUID::class.java),
                rs.getString("token_hash"), rs.getString("display_name"),
                rs.getTimestamp("expires_at").toInstant(), rs.getTimestamp("used_at")?.toInstant(),
                rs.getTimestamp("created_at").toInstant(),
            )
        }.optional().orElse(null)

    override fun createSatellite(satellite: VoiceSatellite) {
        jdbc.sql(
            """INSERT INTO voice_satellite
               (id, owner_id, display_name, hostname, credential_hash, runtime_version, created_at, updated_at)
               VALUES (:id, :ownerId, :displayName, :hostname, :credentialHash, :runtimeVersion,
                       :createdAt, :updatedAt)""",
        ).param("id", satellite.id).param("ownerId", satellite.ownerId)
            .param("displayName", satellite.displayName).param("hostname", satellite.hostname)
            .param("credentialHash", satellite.credentialHash)
            .param("runtimeVersion", satellite.runtimeVersion)
            .param("createdAt", Timestamp.from(satellite.createdAt))
            .param("updatedAt", Timestamp.from(satellite.updatedAt)).update()
    }

    override fun findSatellite(id: UUID): VoiceSatellite? = jdbc.sql(
        "SELECT * FROM voice_satellite WHERE id = :id",
    ).param("id", id).query { rs, _ ->
        VoiceSatellite(
            rs.getObject("id", UUID::class.java), rs.getObject("owner_id", UUID::class.java),
            rs.getString("display_name"), rs.getString("hostname"), rs.getString("credential_hash"),
            rs.getString("runtime_version"), rs.getTimestamp("created_at").toInstant(),
            rs.getTimestamp("updated_at").toInstant(),
        )
    }.optional().orElse(null)

    override fun createSession(session: VoiceDialogueSession) {
        jdbc.sql(
            """INSERT INTO voice_dialogue_session
               (id, satellite_id, owner_id, conversation_id, status, close_reason, started_at,
                last_activity_at, expires_at, closed_at)
               VALUES (:id, :satelliteId, :ownerId, :conversationId, :status, NULL, :startedAt,
                       :lastActivityAt, :expiresAt, NULL)""",
        ).param("id", session.id).param("satelliteId", session.satelliteId)
            .param("ownerId", session.ownerId).param("conversationId", session.conversationId)
            .param("status", session.status).param("startedAt", Timestamp.from(session.startedAt))
            .param("lastActivityAt", Timestamp.from(session.lastActivityAt))
            .param("expiresAt", Timestamp.from(session.expiresAt)).update()
    }

    override fun findSession(id: UUID, satelliteId: UUID): VoiceDialogueSession? = jdbc.sql(
        "SELECT * FROM voice_dialogue_session WHERE id = :id AND satellite_id = :satelliteId",
    ).param("id", id).param("satelliteId", satelliteId).query { rs, _ ->
        VoiceDialogueSession(
            rs.getObject("id", UUID::class.java), rs.getObject("satellite_id", UUID::class.java),
            rs.getObject("owner_id", UUID::class.java), rs.getObject("conversation_id", UUID::class.java),
            rs.getString("status"), rs.getString("close_reason"),
            rs.getTimestamp("started_at").toInstant(), rs.getTimestamp("last_activity_at").toInstant(),
            rs.getTimestamp("expires_at").toInstant(), rs.getTimestamp("closed_at")?.toInstant(),
        )
    }.optional().orElse(null)

    override fun closeSession(id: UUID, satelliteId: UUID, reason: String, closedAt: Instant): Boolean =
        jdbc.sql(
            """UPDATE voice_dialogue_session SET status = 'closed', close_reason = :reason,
               closed_at = :closedAt, last_activity_at = :closedAt
               WHERE id = :id AND satellite_id = :satelliteId AND status = 'active'""",
        ).param("reason", reason).param("closedAt", Timestamp.from(closedAt))
            .param("id", id).param("satelliteId", satelliteId).update() == 1
}

data class CreatedVoiceEnrollment(val id: UUID, val token: String, val expiresAt: Instant)
data class RegisteredVoiceSatellite(val satellite: VoiceSatellite, val token: String)

@Service
class VoiceSatelliteService(
    private val repository: VoiceSatelliteRepository,
    private val tokens: SessionTokenService,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun createEnrollment(ownerId: UUID, displayName: String): CreatedVoiceEnrollment {
        val now = clock.instant()
        val token = tokens.create()
        val enrollment = VoiceSatelliteEnrollment(
            UUID.randomUUID(), ownerId, token.tokenHash, displayName, now.plus(Duration.ofMinutes(15)), null, now,
        )
        repository.createEnrollment(enrollment)
        activity.record(
            ActivityCategory.SECURITY, "voice.satellite.enrollment.created", ActivityStatus.SUCCEEDED,
            ActivityActorType.USER, "kyrion-core", "voice.satellite.enrollment.created", ownerId.toString(), enrollment.id,
        )
        return CreatedVoiceEnrollment(enrollment.id, token.rawToken, enrollment.expiresAt)
    }

    @Transactional
    fun enroll(token: String, hostname: String, runtimeVersion: String): RegisteredVoiceSatellite {
        val now = clock.instant()
        val enrollment = repository.consumeEnrollment(tokens.hash(token), now)
            ?: throw VoiceSatelliteUnauthenticatedException()
        return register(enrollment.ownerId, enrollment.displayName, hostname, runtimeVersion, now)
    }

    fun bootstrap(ownerId: UUID, displayName: String, hostname: String, runtimeVersion: String) =
        register(ownerId, displayName, hostname, runtimeVersion, clock.instant())

    fun openSession(satelliteId: UUID, credential: String): VoiceDialogueSession {
        val satellite = authenticate(satelliteId, credential)
        val now = clock.instant()
        val session = VoiceDialogueSession(
            UUID.randomUUID(), satellite.id, satellite.ownerId, UUID.randomUUID(), "active", null,
            now, now, now.plus(Duration.ofMinutes(15)), null,
        )
        repository.createSession(session)
        activity.record(
            ActivityCategory.SYSTEM, "voice.session.started", ActivityStatus.SUCCEEDED,
            ActivityActorType.INTEGRATION, "kyrion-voice-satellite", "voice.session.started",
            satellite.id.toString(), session.id,
        )
        return session
    }

    fun closeSession(satelliteId: UUID, credential: String, sessionId: UUID, reason: String) {
        authenticate(satelliteId, credential)
        if (!repository.closeSession(sessionId, satelliteId, reason, clock.instant())) {
            throw VoiceSessionNotFoundException()
        }
    }

    fun activeSession(satelliteId: UUID, credential: String, sessionId: UUID): VoiceDialogueSession {
        authenticate(satelliteId, credential)
        val session = repository.findSession(sessionId, satelliteId)
            ?: throw VoiceSessionNotFoundException()
        if (session.status != "active" || session.expiresAt <= clock.instant()) {
            throw VoiceSessionInactiveException()
        }
        return session
    }

    fun authenticate(id: UUID, credential: String): VoiceSatellite =
        repository.findSatellite(id)?.takeIf { it.credentialHash == tokens.hash(credential) }
            ?: throw VoiceSatelliteUnauthenticatedException()

    private fun register(
        ownerId: UUID,
        displayName: String,
        hostname: String,
        runtimeVersion: String,
        now: Instant,
    ): RegisteredVoiceSatellite {
        val credential = tokens.create()
        val satellite = VoiceSatellite(
            UUID.randomUUID(), ownerId, displayName, hostname,
            credential.tokenHash, runtimeVersion, now, now,
        )
        repository.createSatellite(satellite)
        activity.record(
            ActivityCategory.SECURITY, "voice.satellite.registered", ActivityStatus.SUCCEEDED,
            ActivityActorType.INTEGRATION, "kyrion-core", "voice.satellite.registered",
            satellite.id.toString(), satellite.id,
        )
        return RegisteredVoiceSatellite(satellite, credential.rawToken)
    }
}

class VoiceSatelliteUnauthenticatedException : RuntimeException()
class VoiceSessionNotFoundException : RuntimeException()
class VoiceSessionInactiveException : RuntimeException()
