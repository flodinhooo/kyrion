package dev.kyrion.core.calendar

import dev.kyrion.core.ai.AiTestGatewayConfiguration
import dev.kyrion.core.integration.*
import dev.kyrion.core.security.*
import org.assertj.core.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc
import org.springframework.context.annotation.Import
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.*
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer
import java.nio.file.Files
import java.time.Duration
import java.time.Instant
import java.util.UUID

@Testcontainers @SpringBootTest @AutoConfigureMockMvc @Import(AiTestGatewayConfiguration::class)
class PersonalCalendarDisclosureIntegrationTest @Autowired constructor(
    private val jdbc: JdbcClient, private val auth: LocalAuthenticationService,
    private val hashing: PasswordHashingService, private val rbac: RbacService,
    private val service: PersonalCalendarDisclosureService, private val mvc: MockMvc,
) {
    @MockitoBean private lateinit var google: GoogleIntegrationService
    private lateinit var owner: AuthenticatedOwner
    private lateinit var partner: AuthenticatedOwner
    private lateinit var connection: UUID
    private val start = Instant.parse("2026-11-10T10:00:00Z")
    private val end = start.plusSeconds(3600)
    private val calendar = "personal@example.invalid"
    private fun setting(mode: CalendarVisibility, revision: Long = 0) = service.change(partner.user.id, CalendarDisclosureChange(calendar, mode, revision))
    @BeforeEach fun setup() {
        jdbc.sql("TRUNCATE user_account,activity_event,activity_integrity_chain CASCADE").update()
        jdbc.sql("UPDATE installation_bootstrap_state SET initialized=FALSE").update()
        owner = auth.setup("disclosure-owner", password, secret)
        val id = UUID.randomUUID()
        jdbc.sql("INSERT INTO user_account(id,username,password_hash,workspace_owner_id) VALUES(:id,'disclosure-partner',:hash,:space)")
            .param("id", id).param("hash", hashing.hash(password)).param("space", owner.user.id).update()
        rbac.initializeUser(id, owner.user.id, false)
        val role = rbac.createRole(owner.user.id, RoleRequest("personal-calendar", "Personal calendar", setOf("calendar:read", "calendar:update")))
        rbac.assignRoles(owner.user.id, id, setOf(role.id))
        partner = auth.login("disclosure-partner", password)
        connection = connect()
        `when`(google.calendars(partner.user.id)).thenReturn(GoogleCalendars(listOf(GoogleCalendar(calendar, "Secret calendar name", "UTC", "owner"))))
        `when`(google.events(partner.user.id, calendar, start.toString(), end.toString(), connection)).thenReturn(GoogleCalendarEvents(listOf(
            GoogleCalendarEvent("secret-provider-id", "Medical appointment", start.toString(), end.toString(), "secret-etag", description = "Sensitive description", kyrionId = "private-marker"),
            GoogleCalendarEvent("all-day", "Private holiday", "2026-11-10", "2026-11-11"),
            GoogleCalendarEvent("cancelled", "Cancelled", start.toString(), end.toString(), status = "cancelled"),
        )))
    }
    private fun connect(): UUID {
        val id = UUID.randomUUID()
        jdbc.sql("""INSERT INTO integration_connection(id,owner_id,provider,display_name,endpoint_host,credential_ciphertext,credential_nonce,created_at,updated_at)
            VALUES(:id,:user,'google','Private account','private',decode('00','hex'),decode('00','hex'),CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
            .param("id", id).param("user", partner.user.id).update()
        return id
    }
    @Test fun `private by default even for owner and settings stay personal`() {
        assertThat(service.sources(owner.user.id)).isEmpty()
        assertThat(service.settings(owner.user.id)).isEmpty()
        val grant = setting(CalendarVisibility.PRIVATE)
        assertThat(service.sources(owner.user.id)).isEmpty()
        assertThatThrownBy { service.events(owner.user.id, grant.id, start, end) }.hasMessage("CALENDAR_DISCLOSURE_NOT_FOUND")
        verify(google, never()).events(partner.user.id, calendar, start.toString(), end.toString(), connection)
        assertThat(service.settings(owner.user.id)).isEmpty()
        assertThat(service.settings(partner.user.id)).hasSize(1)
    }
    @Test fun `availability redacts every provider detail and preserves all day boundaries`() {
        val grant = setting(CalendarVisibility.AVAILABILITY)
        val result = service.events(owner.user.id, grant.id, start, end)
        assertThat(result.items).hasSize(2)
        assertThat(result.items).allSatisfy { assertThat(it.title).isNull(); assertThat(it.description).isNull(); assertThat(it.id).hasSize(64) }
        assertThat(result.items[1].startsAt).isEqualTo("2026-11-10")
        assertThat(result.items[1].endsAt).isEqualTo("2026-11-11")
        mvc.perform(get("/v1/calendar/personal-disclosure/sources/${grant.id}/events").param("start", start.toString()).param("end", end.toString())
            .header("Authorization", "Bearer ${owner.session.rawToken}")).andExpect(status().isOk)
            .andExpect(header().string("Cache-Control", "no-store"))
            .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("Medical"))))
            .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("secret-"))))
            .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString(calendar))))
    }
    @Test fun `details are read only scoped projection and revocation prevents subsequent fetch`() {
        val grant = setting(CalendarVisibility.DETAILS)
        assertThat(service.events(owner.user.id, grant.id, start, end).items[0].title).isEqualTo("Medical appointment")
        setting(CalendarVisibility.PRIVATE, grant.revision)
        assertThat(service.sources(owner.user.id)).isEmpty()
        assertThatThrownBy { service.events(owner.user.id, grant.id, start, end) }.hasMessage("CALENDAR_DISCLOSURE_NOT_FOUND")
        verify(google, times(1)).events(partner.user.id, calendar, start.toString(), end.toString(), connection)
    }
    @Test fun `downgrade during provider fetch discards previous detailed representation`() {
        val grant = setting(CalendarVisibility.DETAILS)
        `when`(google.events(partner.user.id, calendar, start.toString(), end.toString(), connection)).thenAnswer {
            setting(CalendarVisibility.AVAILABILITY, grant.revision)
            GoogleCalendarEvents(listOf(GoogleCalendarEvent("secret", "Must not escape", start.toString(), end.toString())))
        }
        assertThatThrownBy { service.events(owner.user.id, grant.id, start, end) }.hasMessage("CALENDAR_DISCLOSURE_CONFLICT")
    }
    @Test fun `private revocation during provider request returns no previous details`() {
        val grant = setting(CalendarVisibility.DETAILS)
        `when`(google.events(partner.user.id, calendar, start.toString(), end.toString(), connection)).thenAnswer {
            setting(CalendarVisibility.PRIVATE, grant.revision)
            GoogleCalendarEvents(listOf(GoogleCalendarEvent("secret", "Must not escape", start.toString(), end.toString())))
        }
        assertThatThrownBy { service.events(owner.user.id, grant.id, start, end) }.hasMessage("CALENDAR_DISCLOSURE_NOT_FOUND")
    }
    @Test fun `source account deactivation during provider request prevents result disclosure`() {
        val grant = setting(CalendarVisibility.DETAILS)
        `when`(google.events(partner.user.id, calendar, start.toString(), end.toString(), connection)).thenAnswer {
            rbac.deactivate(owner.user.id, partner.user.id, false)
            GoogleCalendarEvents(listOf(GoogleCalendarEvent("secret", "Must not escape", start.toString(), end.toString())))
        }
        assertThatThrownBy { service.events(owner.user.id, grant.id, start, end) }.hasMessage("CALENDAR_DISCLOSURE_NOT_FOUND")
    }
    @Test fun `HTTP setting change is personal revisioned and visible only after explicit consent`() {
        mvc.perform(put("/v1/calendar/personal-disclosure").header("Authorization", "Bearer ${partner.session.rawToken}")
            .contentType("application/json").content("""{"calendarId":"$calendar","visibility":"DETAILS","revision":0}"""))
            .andExpect(status().isOk).andExpect(jsonPath("$.revision").value(1))
            .andExpect(header().string("Cache-Control", "no-store"))
        mvc.perform(get("/v1/calendar/personal-disclosure/sources").header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$[0].userId").value(partner.user.id.toString()))
            .andExpect(jsonPath("$[0].calendarId").doesNotExist()).andExpect(jsonPath("$[0].username").value("disclosure-partner"))
        assertThatThrownBy { service.change(owner.user.id, CalendarDisclosureChange(calendar, CalendarVisibility.PRIVATE, 1)) }
            .hasMessage("CALENDAR_DISCLOSURE_NOT_FOUND")
        assertThat(service.settings(partner.user.id).single().visibility).isEqualTo(CalendarVisibility.DETAILS)
    }
    @Test fun `owner and reader permission revocation and deactivation suppress sources`() {
        val grant = setting(CalendarVisibility.DETAILS)
        val role = rbac.createRole(owner.user.id, RoleRequest("no-calendar", "No calendar", setOf("devices:read")))
        rbac.assignRoles(owner.user.id, partner.user.id, setOf(role.id))
        assertThat(service.sources(owner.user.id)).isEmpty()
        assertThatThrownBy { service.events(owner.user.id, grant.id, start, end) }.hasMessage("CALENDAR_DISCLOSURE_NOT_FOUND")
        assertThatThrownBy { service.sources(partner.user.id) }.isInstanceOf(ForbiddenException::class.java)
        rbac.deactivate(owner.user.id, partner.user.id, false)
        assertThat(service.sources(owner.user.id)).isEmpty()
    }
    @Test fun `disconnect destroys grants and reconnect never restores them`() {
        val grant = setting(CalendarVisibility.DETAILS)
        jdbc.sql("DELETE FROM integration_connection WHERE id=:id").param("id", connection).update()
        connect()
        assertThat(service.settings(partner.user.id)).isEmpty()
        assertThat(service.sources(owner.user.id)).isEmpty()
        assertThatThrownBy { service.events(owner.user.id, grant.id, start, end) }.hasMessage("CALENDAR_DISCLOSURE_NOT_FOUND")
    }
    @Test fun `foreign household and business never read personal source`() {
        val grant = setting(CalendarVisibility.DETAILS)
        val foreign = UUID.randomUUID()
        jdbc.sql("INSERT INTO user_account(id,username,password_hash) VALUES(:id,'foreign-disclosure',:hash)")
            .param("id", foreign).param("hash", hashing.hash(password)).update()
        rbac.initializeUser(foreign, foreign, true)
        assertThat(service.sources(foreign)).isEmpty()
        assertThatThrownBy { service.events(foreign, grant.id, start, end) }.hasMessage("CALENDAR_DISCLOSURE_NOT_FOUND")
        jdbc.sql("UPDATE kyrion_space SET type='BUSINESS' WHERE id=:space").param("space", owner.user.id).update()
        assertThatThrownBy { service.sources(owner.user.id) }.isInstanceOf(ForbiddenException::class.java)
    }
    @Test fun `stale changes and forged identity invalid range and primary aliases fail`() {
        val grant = setting(CalendarVisibility.DETAILS)
        assertThatThrownBy { setting(CalendarVisibility.PRIVATE) }.hasMessage("CALENDAR_DISCLOSURE_CONFLICT")
        assertThatThrownBy { service.events(owner.user.id, grant.id, start, start.plus(Duration.ofDays(401))) }.hasMessage("CALENDAR_DISCLOSURE_INVALID")
        assertThatThrownBy { service.change(partner.user.id, CalendarDisclosureChange("primary", CalendarVisibility.DETAILS, 0)) }.hasMessage("CALENDAR_DISCLOSURE_INVALID")
        for (body in listOf("""{"calendarId":"$calendar","visibility":"PRIVATE","revision":1,"userId":"${partner.user.id}"}""",
                """{"calendarId":"$calendar","visibility":"PRIVATE","revision":"1"}""",
                """{"calendarId":"$calendar","visibility":"PRIVATE","revision":1.1}""")) {
            mvc.perform(put("/v1/calendar/personal-disclosure").header("Authorization", "Bearer ${owner.session.rawToken}")
                .contentType("application/json").content(body)).andExpect(status().isBadRequest)
        }
    }
    @Test fun `audit failure rolls back disclosure mutation`() {
        jdbc.sql("ALTER TABLE activity_event ADD CONSTRAINT disclosure_test_failure CHECK(event_type<>'calendar.disclosure.changed') NOT VALID").update()
        try {
            assertThatThrownBy { setting(CalendarVisibility.DETAILS) }.isInstanceOf(org.springframework.dao.DataIntegrityViolationException::class.java)
            assertThat(service.settings(partner.user.id)).isEmpty()
        } finally { jdbc.sql("ALTER TABLE activity_event DROP CONSTRAINT disclosure_test_failure").update() }
    }
    @Test fun `private revocation works while provider is offline and audit contains no calendar data`() {
        val grant = setting(CalendarVisibility.DETAILS)
        `when`(google.calendars(partner.user.id)).thenThrow(GoogleProviderUnavailableException())
        setting(CalendarVisibility.PRIVATE, grant.revision)
        assertThat(service.sources(owner.user.id)).isEmpty()
        val summaries = jdbc.sql("SELECT summary_code FROM activity_event WHERE event_type='calendar.disclosure.changed'").query(String::class.java).list()
        assertThat(summaries).containsOnly(grant.id.toString())
    }
    companion object {
        private const val password = "secure-personal-calendar-password"
        private val secret = SessionTokenService().create().rawToken
        private val temp = Files.createTempDirectory("kyrion-disclosure-test-")
        private val bootstrap = temp.resolve("bootstrap").also { Files.writeString(it, secret) }
        private val key = temp.resolve("key").also { Files.write(it, ByteArray(32) { (it + 1).toByte() }) }
        @Container @JvmStatic val postgres = PostgreSQLContainer("postgres:17-alpine").withTmpFs(mapOf("/var/lib/postgresql/data" to "rw")).withStartupTimeout(Duration.ofMinutes(3))
        @DynamicPropertySource @JvmStatic fun properties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url", postgres::getJdbcUrl)
            registry.add("spring.datasource.username", postgres::getUsername)
            registry.add("spring.datasource.password", postgres::getPassword)
            registry.add("kyrion.security.bootstrap-secret-file") { bootstrap.toString() }
            registry.add("kyrion.audit.integrity-key-file") { key.toString() }
            registry.add("kyrion.credentials.key-file") { key.toString() }
            registry.add("kyrion.knowledge.root") { temp.resolve("documents").toString() }
            registry.add("kyrion.knowledge.worker-enabled") { "false" }
            registry.add("kyrion.calendar.sync.scheduler-enabled") { "false" }
            registry.add("kyrion.home-assistant.refresh-enabled") { "false" }
        }
    }
}
