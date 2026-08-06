package dev.kyrion.core.gateway

import dev.kyrion.core.activity.ActivityEvent
import dev.kyrion.core.activity.ActivityEventRepository
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.security.SessionTokenService
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset
import java.util.UUID

class GatewayServiceTest {
    private val now = Instant.parse("2026-08-06T13:00:00Z")
    private val clock = Clock.fixed(now, ZoneOffset.UTC)
    private val repository = FakeGatewayRepository()
    private val service = GatewayService(
        repository, SessionTokenService(), ActivityService(FakeActivityRepository(), clock), clock,
    )

    @Test
    fun `enrollment is one time and stores only token hashes`() {
        val ownerId = UUID.randomUUID()
        val enrollment = service.createEnrollment(ownerId, "kyrion-node")

        assertThat(repository.enrollments.single().tokenHash).doesNotContain(enrollment.enrollmentToken)
        val registered = service.enroll(
            enrollment.enrollmentToken, "kyrion-node", "0.1.0", "Debian", "13", "aarch64",
        )

        assertThat(registered.node.ownerId).isEqualTo(ownerId)
        assertThat(registered.node.credentialHash).doesNotContain(registered.gatewayToken)
        assertThatThrownBy {
            service.enroll(enrollment.enrollmentToken, "other", "0.1.0", "Debian", "13", "aarch64")
        }.isInstanceOf(GatewayEnrollmentInvalidException::class.java)
    }

    @Test
    fun `heartbeat requires node credential and exposes typed online health`() {
        val enrollment = service.createEnrollment(UUID.randomUUID(), "kyrion-node")
        val registered = service.enroll(
            enrollment.enrollmentToken, "kyrion-node", "0.1.0", "Debian", "13", "aarch64",
        )
        val health = validHealth()

        service.heartbeat(registered.node.id, registered.gatewayToken, health)

        val view = service.all(registered.node.ownerId).single()
        assertThat(view.availability).isEqualTo("online")
        assertThat(view.health).isEqualTo(health)
        assertThatThrownBy { service.heartbeat(registered.node.id, "wrong", health) }
            .isInstanceOf(GatewayUnauthenticatedException::class.java)
    }

    @Test
    fun `heartbeat rejects impossible untrusted metrics`() {
        val enrollment = service.createEnrollment(UUID.randomUUID(), "kyrion-node")
        val registered = service.enroll(
            enrollment.enrollmentToken, "kyrion-node", "0.1.0", "Debian", "13", "aarch64",
        )

        assertThatThrownBy {
            service.heartbeat(registered.node.id, registered.gatewayToken, validHealth().copy(temperatureCelsius = 400.0))
        }.isInstanceOf(GatewayHealthInvalidException::class.java)
    }

    private fun validHealth() = GatewayHealth(
        42.2, false, 8_000, 7_000, 64_000, 48_000,
        GatewayInterfaceHealth(true, true), GatewayInterfaceHealth(true, false),
        true, true, "running", listOf(GatewayServiceHealth("zigbee", "not_configured")),
    )

    private inner class FakeGatewayRepository : GatewayRepository {
        val enrollments = mutableListOf<GatewayEnrollment>()
        val nodes = mutableListOf<GatewayNode>()

        override fun createEnrollment(enrollment: GatewayEnrollment) { enrollments += enrollment }
        override fun consumeEnrollment(tokenHash: String, usedAt: Instant): GatewayEnrollment? {
            val index = enrollments.indexOfFirst { it.tokenHash == tokenHash && it.usedAt == null && it.expiresAt > usedAt }
            if (index < 0) return null
            return enrollments[index].copy(usedAt = usedAt).also { enrollments[index] = it }
        }
        override fun create(node: GatewayNode) { nodes += node }
        override fun all(ownerId: UUID) = nodes.filter { it.ownerId == ownerId }
        override fun findById(id: UUID) = nodes.singleOrNull { it.id == id }
        override fun updateHeartbeat(id: UUID, credentialHash: String, health: GatewayHealth, seenAt: Instant): Boolean {
            val index = nodes.indexOfFirst { it.id == id && it.credentialHash == credentialHash }
            if (index < 0) return false
            nodes[index] = nodes[index].copy(health = health, lastSeenAt = seenAt, updatedAt = seenAt)
            return true
        }
    }

    private class FakeActivityRepository : ActivityEventRepository {
        private val events = mutableListOf<ActivityEvent>()
        override fun append(event: ActivityEvent) = event.also(events::add)
        override fun findRecent(limit: Int) = events.takeLast(limit).reversed()
    }
}
