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
    fun `expected Space cannot redirect or consume another Space code`() {
        val owner = UUID.randomUUID()
        val enrollment = service.createEnrollment(owner, "bound")
        val credential = SessionTokenService().create().rawToken
        assertThatThrownBy {
            service.enroll(enrollment.enrollmentToken, "bound", "1", "Windows", "test", "amd64", credential, UUID.randomUUID())
        }.isInstanceOf(GatewayEnrollmentInvalidException::class.java)
        assertThat(repository.enrollments.single().usedAt).isNull()
        assertThat(repository.nodes).isEmpty()
        val result = service.enroll(enrollment.enrollmentToken, "bound", "1", "Windows", "test", "amd64", credential, owner)
        assertThat(result.node.ownerId).isEqualTo(owner)
        assertThatThrownBy {
            service.enroll(enrollment.enrollmentToken, "bound", "1", "Windows", "test", "amd64", credential, UUID.randomUUID())
        }.isInstanceOf(GatewayEnrollmentInvalidException::class.java)
        val acknowledged = service.enroll(enrollment.enrollmentToken, "bound", "1", "Windows", "test", "amd64", credential, owner)
        assertThat(acknowledged.node.id).isEqualTo(result.node.id)
        assertThat(repository.nodes).hasSize(1)
    }

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
    fun `same prepared credential acknowledges lost response without another node`() {
        val enrollment = service.createEnrollment(UUID.randomUUID(), "prepared")
        val credential = SessionTokenService().create().rawToken
        val first = service.enroll(enrollment.enrollmentToken, "prepared", "1", "Debian", "13", "amd64", credential)
        val retry = service.enroll(enrollment.enrollmentToken, "prepared", "1", "Debian", "13", "amd64", credential)
        assertThat(retry.node.id).isEqualTo(first.node.id)
        assertThat(retry.gatewayToken).isEqualTo(credential)
        assertThat(repository.nodes).hasSize(1)
        assertThat(repository.nodes.single().enrollmentId).isEqualTo(enrollment.id)
        assertThat(repository.nodes.single().credentialHash).isEqualTo(SessionTokenService().hash(credential))
    }

    @Test
    fun `consumed enrollment cannot be reused by a different credential or identity`() {
        val enrollment = service.createEnrollment(UUID.randomUUID(), "prepared")
        val credential = SessionTokenService().create().rawToken
        service.enroll(enrollment.enrollmentToken, "prepared", "1", "Debian", "13", "amd64", credential)
        val identities = listOf(
            listOf("other", "1", "Debian", "13", "amd64", credential),
            listOf("prepared", "2", "Debian", "13", "amd64", credential),
            listOf("prepared", "1", "Windows", "13", "amd64", credential),
            listOf("prepared", "1", "Debian", "14", "amd64", credential),
            listOf("prepared", "1", "Debian", "13", "arm64", credential),
            listOf("prepared", "1", "Debian", "13", "amd64", SessionTokenService().create().rawToken),
        )
        identities.forEach { values ->
            assertThatThrownBy { service.enroll(enrollment.enrollmentToken, values[0], values[1], values[2], values[3], values[4], values[5]) }
                .isInstanceOf(GatewayEnrollmentInvalidException::class.java)
        }
        assertThat(repository.nodes).hasSize(1)
    }

    @Test
    fun `acknowledgement expires at original enrollment deadline`() {
        val enrollment = service.createEnrollment(UUID.randomUUID(), "prepared")
        val credential = SessionTokenService().create().rawToken
        service.enroll(enrollment.enrollmentToken, "prepared", "1", "Debian", "13", "amd64", credential)
        val expired = GatewayService(repository, SessionTokenService(), ActivityService(FakeActivityRepository(), clock),
            Clock.fixed(enrollment.expiresAt, ZoneOffset.UTC))
        assertThatThrownBy { expired.enroll(enrollment.enrollmentToken, "prepared", "1", "Debian", "13", "amd64", credential) }
            .isInstanceOf(GatewayEnrollmentInvalidException::class.java)
        assertThat(repository.nodes).hasSize(1)
    }

    @Test
    fun `legacy server generated enrollment is still strictly one use`() {
        val enrollment = service.createEnrollment(UUID.randomUUID(), "legacy")
        val legacy = service.enroll(enrollment.enrollmentToken, "legacy", "1", "Debian", "13", "amd64")
        assertThat(legacy.node.enrollmentId).isNull()
        assertThatThrownBy { service.enroll(enrollment.enrollmentToken, "legacy", "1", "Debian", "13", "amd64", legacy.gatewayToken) }
            .isInstanceOf(GatewayEnrollmentInvalidException::class.java)
    }

    @Test
    fun `malformed prepared credentials do not consume authorization`() {
        val enrollment = service.createEnrollment(UUID.randomUUID(), "prepared")
        listOf("", "short", "a".repeat(43), "A".repeat(42), "*".repeat(43)).forEach { credential ->
            assertThatThrownBy { service.enroll(enrollment.enrollmentToken, "prepared", "1", "Debian", "13", "amd64", credential) }
                .isInstanceOf(GatewayEnrollmentInvalidException::class.java)
        }
        assertThat(repository.enrollments.single().usedAt).isNull()
        assertThat(repository.nodes).isEmpty()
    }

    @Test
    fun `acknowledgement cannot cross enrollment Space boundary`() {
        val enrollment = service.createEnrollment(UUID.randomUUID(), "prepared")
        val credential = SessionTokenService().create().rawToken
        service.enroll(enrollment.enrollmentToken, "prepared", "1", "Debian", "13", "amd64", credential)
        repository.nodes[0] = repository.nodes[0].copy(ownerId = UUID.randomUUID())
        assertThatThrownBy { service.enroll(enrollment.enrollmentToken, "prepared", "1", "Debian", "13", "amd64", credential) }
            .isInstanceOf(GatewayEnrollmentInvalidException::class.java)
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

    @Test
    fun `heartbeat rejects unsupported bluetooth devices`() {
        val enrollment = service.createEnrollment(UUID.randomUUID(), "kyrion-node")
        val registered = service.enroll(
            enrollment.enrollmentToken, "kyrion-node", "0.1.0", "Debian", "13", "aarch64",
        )
        val invalid = GatewayBluetoothDevice(
            "C7:7C:08:10:37:EA", "Unknown", "OA20", true, null, null, null, null,
        )

        assertThatThrownBy {
            service.heartbeat(
                registered.node.id, registered.gatewayToken,
                validHealth().copy(bluetoothDevices = listOf(invalid)),
            )
        }.isInstanceOf(GatewayHealthInvalidException::class.java)
    }

    private fun validHealth() = GatewayHealth(
        42.2, false, 8_000, 7_000, 64_000, 48_000,
        GatewayInterfaceHealth(true, true), GatewayInterfaceHealth(true, false),
        true, true, "running",
        listOf(GatewayAdapterHealth("sonoff", "zigbee", "Itead", "Sonoff", "serial", "/dev/serial/by-id/sonoff")),
        GatewayAudioHealth(
            GatewayAudioEndpoint("alsa_input.usb-delock", "Delock microphone", "usb"),
            GatewayAudioEndpoint("bluez_output.pebble", "Pebble V3", "bluetooth"),
        ),
        GatewayZigbeeHealth(false, 15, emptyList()),
        listOf(GatewayServiceHealth("zigbee", "not_configured")),
    )

    private inner class FakeGatewayRepository : GatewayRepository {
        val enrollments = mutableListOf<GatewayEnrollment>()
        val nodes = mutableListOf<GatewayNode>()

        override fun createEnrollment(enrollment: GatewayEnrollment) { enrollments += enrollment }
        override fun consumeEnrollment(tokenHash: String, usedAt: Instant, expectedSpaceId: UUID?): GatewayEnrollment? {
            val index = enrollments.indexOfFirst { it.tokenHash == tokenHash && it.usedAt == null && it.expiresAt > usedAt &&
                (expectedSpaceId == null || it.ownerId == expectedSpaceId) }
            if (index < 0) return null
            return enrollments[index].copy(usedAt = usedAt).also { enrollments[index] = it }
        }
        override fun consumedEnrollment(tokenHash: String, now: Instant) =
            enrollments.singleOrNull { it.tokenHash == tokenHash && it.usedAt != null && it.expiresAt > now }
        override fun findByEnrollment(id: UUID) = nodes.singleOrNull { it.enrollmentId == id }
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
