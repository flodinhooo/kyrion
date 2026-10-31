package dev.kyrion.core.ai

import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.security.RbacService
import java.time.Clock
import java.time.Instant
import java.time.ZoneId
import java.time.ZoneOffset
import java.util.UUID
import org.assertj.core.api.Assertions.assertThat
import org.junit.jupiter.api.Test
import org.mockito.ArgumentMatchers.any
import org.mockito.ArgumentMatchers.anyString
import org.mockito.Mockito.*
import org.springframework.jdbc.core.RowMapper
import org.springframework.jdbc.core.simple.JdbcClient

class AiUsageServiceTest {
    private val actor = UUID.randomUUID()
    private val jdbc = mock(JdbcClient::class.java)
    private val statement = mock(JdbcClient.StatementSpec::class.java, RETURNS_SELF)
    private val settings = mock(AiSettingsService::class.java, RETURNS_DEEP_STUBS)
    private val rbac = mock(RbacService::class.java)
    private val activity = mock(ActivityService::class.java)
    private val clock = MonthBoundaryClock()
    private val service = AiUsageService(jdbc, settings, rbac, activity, clock)
    private val model = AiTestGateway().model
    private val reservation = AiReservation(UUID.randomUUID(), 116, 100, model, null)

    init {
        `when`(jdbc.sql(anyString())).thenReturn(statement)
        val rows = mock<JdbcClient.MappedQuerySpec<AiUsageRow>>()
        `when`(statement.query(any<RowMapper<AiUsageRow>>())).thenReturn(rows)
        `when`(rows.list()).thenReturn(emptyList())
        `when`(settings.repository.preferences(actor)).thenReturn(AiPreferences())
        `when`(settings.effectivePolicy(actor)).thenReturn(AiPolicy())
        val account = mock<JdbcClient.MappedQuerySpec<UUID?>>()
        `when`(statement.query(UUID::class.java)).thenReturn(account)
        `when`(account.single()).thenReturn(actor)
        `when`(account.optional()).thenReturn(java.util.Optional.of(actor))
    }

    @Test
    fun `summary uses one UTC period for its label and counters across midnight`() {
        val summary = service.summary(actor)

        assertThat(summary.period).isEqualTo("2026-10")
        assertThat(clock.reads).isEqualTo(1)
        verify(statement).param("period", summary.period)
    }

    @Test
    fun `reservation checks and inserts into the same month across midnight`() {
        val account = mock<JdbcClient.MappedQuerySpec<UUID?>>()
        `when`(statement.query(UUID::class.java)).thenReturn(account)
        `when`(account.single()).thenReturn(actor)
        `when`(statement.update()).thenReturn(1)

        service.reserve(actor, UUID.randomUUID(), 0, model, AiRouteRequest(), AiCatalog(model.id, listOf(model)), 100)

        assertThat(clock.reads).isEqualTo(1)
        verify(statement, times(2)).param("period", "2026-10")
        verify(statement, never()).param("period", "2026-11")
    }

    @Test
    fun `settlement writes an audit event only when the pending attempt changes`() {
        `when`(statement.update()).thenReturn(1, 0)

        service.settle(actor, reservation, 12, 2, 14, true, null)
        service.settle(actor, reservation, 12, 2, 14, true, null)

        assertThat(mockingDetails(activity).invocations).hasSize(1)
    }

    @Test
    fun `uninvoked release writes an audit event only when the pending attempt changes`() {
        `when`(statement.update()).thenReturn(1, 0)

        service.releaseUninvoked(actor, reservation, "POLICY_CHANGED")
        service.releaseUninvoked(actor, reservation, "POLICY_CHANGED")

        assertThat(mockingDetails(activity).invocations).hasSize(1)
    }

    @Test
    fun `missing foreign or already finalized attempts produce no completion audit`() {
        `when`(statement.update()).thenReturn(0)

        service.settle(actor, reservation, 12, 2, 14, true, null)
        service.releaseUninvoked(actor, reservation, "POLICY_CHANGED")

        verifyNoInteractions(activity)
    }

    @Test
    fun `provider counters reject negative oversized and contradictory totals without overflowing`() {
        assertThat(validAiUsage(null, null, null)).isTrue()
        assertThat(validAiUsage(0, 0, 0)).isTrue()
        assertThat(validAiUsage(12, 2, 14)).isTrue()
        assertThat(validAiUsage(12, 2, 20)).isTrue() // Extra provider categories remain conservatively priced.
        assertThat(validAiUsage(12, 2, 0)).isFalse()
        assertThat(validAiUsage(12, null, 0)).isFalse()
        assertThat(validAiUsage(-1, 2, 1)).isFalse()
        assertThat(validAiUsage(Long.MAX_VALUE, Long.MAX_VALUE, null)).isFalse()
    }

    private class MonthBoundaryClock : Clock() {
        var reads = 0
        override fun getZone(): ZoneId = ZoneOffset.UTC
        override fun withZone(zone: ZoneId): Clock = this
        override fun instant(): Instant = if (reads++ == 0) {
            Instant.parse("2026-10-31T23:59:59.999Z")
        } else {
            Instant.parse("2026-11-01T00:00:00Z")
        }
    }
}
