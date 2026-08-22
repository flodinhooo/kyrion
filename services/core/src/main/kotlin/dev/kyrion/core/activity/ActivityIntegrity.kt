package dev.kyrion.core.activity

import org.springframework.beans.factory.annotation.Value
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Component
import java.nio.charset.StandardCharsets
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardOpenOption
import java.security.MessageDigest
import java.security.SecureRandom
import java.sql.Timestamp
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.UUID
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

@Component
class ActivityIntegrity(
    @Value("\${kyrion.audit.integrity-key-file:E:/Kyrion/Data/secrets/audit-integrity.key}") keyFile: String,
) {
    private val key = SecretKeySpec(loadOrCreateKey(keyFile), "HmacSHA256")

    fun eventHash(event: ActivityEvent, scope: String, previousHash: ByteArray?): ByteArray = authenticate(
        listOf(
            "event-v1", scope, previousHash?.hex().orEmpty(), event.id.toString(), event.occurredAt.truncatedTo(ChronoUnit.MICROS).toString(),
            event.category.name, event.eventType, event.status.name, event.actorType.name, event.actorId.orEmpty(),
            event.source, event.correlationId.toString(), event.summaryCode, event.ownerId?.toString().orEmpty(),
        ).joinToString("\u001f"),
    )

    fun anchorMac(scope: String, previousHash: ByteArray?): ByteArray =
        authenticate("anchor-v1\u001f$scope\u001f${previousHash?.hex().orEmpty()}")

    fun matches(expected: ByteArray, actual: ByteArray?) = actual != null && MessageDigest.isEqual(expected, actual)

    private fun authenticate(value: String): ByteArray = Mac.getInstance("HmacSHA256").run {
        init(key)
        doFinal(value.toByteArray(StandardCharsets.UTF_8))
    }

    private fun loadOrCreateKey(value: String): ByteArray {
        val path = Path.of(value).toAbsolutePath().normalize()
        Files.createDirectories(path.parent)
        if (Files.exists(path)) return Files.readAllBytes(path).also { require(it.size == 32) }
        return ByteArray(32).also(SecureRandom()::nextBytes).also {
            Files.write(path, it, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)
        }
    }

    private fun ByteArray.hex() = joinToString("") { "%02x".format(it) }
}

data class ActivityIntegrityChainReport(
    val scope: String,
    val valid: Boolean,
    val sealedEvents: Int,
    val legacyEvents: Int,
    val authorizedPruning: Boolean,
)

@Component
class ActivityIntegrityVerifier(private val jdbc: JdbcClient, private val integrity: ActivityIntegrity) {
    fun verify(scope: String): ActivityIntegrityChainReport {
        val head = jdbc.sql("SELECT last_event_id,last_hash,anchor_previous_hash,anchor_mac FROM activity_integrity_chain WHERE chain_scope=:scope")
            .param("scope", scope).query { rs, _ -> ChainHead(rs.getObject(1, UUID::class.java), rs.getBytes(2), rs.getBytes(3), rs.getBytes(4)) }.optional().orElse(null)
        val events = jdbc.sql("""SELECT id,occurred_at,category,event_type,status,actor_type,actor_id,source,correlation_id,summary_code,owner_id,previous_hash,event_hash
            FROM activity_event WHERE chain_scope=:scope AND integrity_version=1 ORDER BY integrity_sequence""")
            .param("scope", scope).query { rs, _ -> SealedEvent(
                ActivityEvent(rs.getObject("id",UUID::class.java),rs.getTimestamp("occurred_at").toInstant(),ActivityCategory.valueOf(rs.getString("category")),rs.getString("event_type"),ActivityStatus.valueOf(rs.getString("status")),ActivityActorType.valueOf(rs.getString("actor_type")),rs.getString("actor_id"),rs.getString("source"),rs.getObject("correlation_id",UUID::class.java),rs.getString("summary_code"),rs.getObject("owner_id",UUID::class.java)),
                rs.getBytes("previous_hash"),rs.getBytes("event_hash"),
            ) }.list()
        val legacy = if (scope == SYSTEM_SCOPE) jdbc.sql("SELECT COUNT(*) FROM activity_event WHERE owner_id IS NULL AND integrity_version IS NULL").query(Int::class.java).single()
        else jdbc.sql("SELECT COUNT(*) FROM activity_event WHERE owner_id=:owner AND integrity_version IS NULL").param("owner",UUID.fromString(scope)).query(Int::class.java).single()
        if (head == null) return ActivityIntegrityChainReport(scope, events.isEmpty(), events.size, legacy, false)
        var expectedPrevious = head.anchorPreviousHash
        var valid = integrity.matches(integrity.anchorMac(scope, expectedPrevious), head.anchorMac)
        events.forEach { sealed ->
            valid = valid && hashesEqual(expectedPrevious, sealed.previousHash)
            valid = valid && integrity.matches(integrity.eventHash(sealed.event, scope, sealed.previousHash), sealed.eventHash)
            expectedPrevious = sealed.eventHash
        }
        valid = valid && hashesEqual(expectedPrevious, head.lastHash) && (events.lastOrNull()?.event?.id == head.lastEventId || events.isEmpty())
        return ActivityIntegrityChainReport(scope, valid, events.size, legacy, head.anchorPreviousHash != null)
    }

    private fun hashesEqual(first: ByteArray?, second: ByteArray?) =
        if (first == null || second == null) first == null && second == null else MessageDigest.isEqual(first, second)
    private data class ChainHead(val lastEventId: UUID?, val lastHash: ByteArray?, val anchorPreviousHash: ByteArray?, val anchorMac: ByteArray?)
    private data class SealedEvent(val event: ActivityEvent, val previousHash: ByteArray?, val eventHash: ByteArray)
}

@Component
class ActivityIntegrityPruner(private val jdbc: JdbcClient, private val integrity: ActivityIntegrity) {
    fun authorizeOwnerPrefix(ownerId: UUID, cutoff: Instant) {
        val scope = ownerId.toString()
        val headExists = jdbc.sql("SELECT COUNT(*) FROM activity_integrity_chain WHERE chain_scope=:scope")
            .param("scope", scope).query(Int::class.java).single() > 0
        if (!headExists) return
        jdbc.sql("SELECT last_hash FROM activity_integrity_chain WHERE chain_scope=:scope FOR UPDATE")
            .param("scope", scope).query(ByteArray::class.java).optional()
        val maximumDeletedSequence = jdbc.sql("SELECT MAX(integrity_sequence) FROM activity_event WHERE chain_scope=:scope AND integrity_version=1 AND occurred_at<:cutoff")
            .param("scope", scope).param("cutoff", Timestamp.from(cutoff)).query(Long::class.java).optional().orElse(null) ?: return
        val retainedBeforeGap = jdbc.sql("SELECT COUNT(*) FROM activity_event WHERE chain_scope=:scope AND integrity_version=1 AND integrity_sequence<:sequence AND occurred_at>=:cutoff")
            .param("scope", scope).param("sequence", maximumDeletedSequence).param("cutoff", Timestamp.from(cutoff)).query(Int::class.java).single()
        if (retainedBeforeGap > 0) throw ActivityIntegrityPruningException()
        val firstRemainingPrevious = jdbc.sql("SELECT previous_hash FROM activity_event WHERE chain_scope=:scope AND integrity_version=1 AND occurred_at>=:cutoff ORDER BY integrity_sequence LIMIT 1")
            .param("scope", scope).param("cutoff", Timestamp.from(cutoff)).query(ByteArray::class.java).optional().orElseGet {
                jdbc.sql("SELECT last_hash FROM activity_integrity_chain WHERE chain_scope=:scope")
                    .param("scope", scope).query(ByteArray::class.java).optional().orElse(null)
            }
        jdbc.sql("UPDATE activity_integrity_chain SET anchor_previous_hash=:anchor,anchor_mac=:mac,updated_at=CURRENT_TIMESTAMP WHERE chain_scope=:scope")
            .param("anchor", firstRemainingPrevious).param("mac", integrity.anchorMac(scope, firstRemainingPrevious)).param("scope", scope).update()
    }
}

class ActivityIntegrityPruningException : RuntimeException()

const val SYSTEM_SCOPE = "system"
