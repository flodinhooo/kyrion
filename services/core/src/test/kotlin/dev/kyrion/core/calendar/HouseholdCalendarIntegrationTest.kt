package dev.kyrion.core.calendar

import dev.kyrion.core.ai.AiTestGatewayConfiguration
import dev.kyrion.core.security.*
import org.assertj.core.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc
import org.springframework.context.annotation.Import
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
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

@Testcontainers
@SpringBootTest
@AutoConfigureMockMvc
@Import(AiTestGatewayConfiguration::class)
class HouseholdCalendarIntegrationTest @Autowired constructor(
    private val jdbc: JdbcClient, private val auth: LocalAuthenticationService,
    private val hashing: PasswordHashingService, private val rbac: RbacService,
    private val service: HouseholdCalendarService, private val mvc: MockMvc,
) {
    private lateinit var owner: AuthenticatedOwner
    private lateinit var partner: AuthenticatedOwner
    private lateinit var other: AuthenticatedOwner
    private val start = Instant.parse("2026-11-10T10:00:00Z")

    @BeforeEach fun setup() {
        jdbc.sql("TRUNCATE user_account,activity_event,activity_integrity_chain CASCADE").update()
        jdbc.sql("UPDATE installation_bootstrap_state SET initialized=FALSE").update()
        owner = auth.setup("family-owner", password, secret)
        partner = member("family-partner")
        other = member("family-other")
    }

    private fun member(name: String, space: UUID = owner.user.id): AuthenticatedOwner {
        val id = UUID.randomUUID()
        jdbc.sql("INSERT INTO user_account(id,username,password_hash,workspace_owner_id) VALUES(:id,:name,:hash,:space)")
            .param("id", id).param("name", name).param("hash", hashing.hash(password)).param("space", space).update()
        rbac.initializeUser(id, space, false)
        val role = rbac.createRole(space, RoleRequest("calendar-${id}", "Calendar member",
            setOf("calendar:read", "calendar:create", "calendar:update", "calendar:delete")))
        rbac.assignRoles(space, id, setOf(role.id))
        return auth.login(name, password)
    }

    private fun create(actor: UUID = owner.user.id, participants: List<UUID> = listOf(partner.user.id)) =
        service.create(actor, HouseholdEventCreate("Family dinner", start, start.plusSeconds(3600), "Europe/Zurich", "Private event details", participants))

    private fun update(event: HouseholdCalendarEvent, title: String = "Changed together") =
        HouseholdEventUpdate(title, event.startsAt, event.endsAt, event.timeZone, event.revision, event.description)

    @Test fun `selected partner edits same canonical event and creator alone can delete`() {
        val event = create()
        assertThat(event.participantIds).containsExactlyInAnyOrder(owner.user.id, partner.user.id)
        val visible = service.all(partner.user.id).single()
        assertThat(visible.canEdit).isTrue()
        assertThat(visible.canDelete).isFalse()
        val changed = service.update(partner.user.id, event.id, update(event))
        assertThat(changed.id).isEqualTo(event.id)
        assertThat(changed.revision).isEqualTo(1)
        assertThat(service.all(owner.user.id).single().title).isEqualTo("Changed together")
        assertThatThrownBy { service.delete(partner.user.id, event.id, changed.revision) }.isInstanceOf(ForbiddenException::class.java)
        service.delete(owner.user.id, event.id, changed.revision)
        assertThat(service.all(partner.user.id)).isEmpty()
        val row = jdbc.sql("SELECT actor_id,owner_id,correlation_id,summary_code FROM activity_event WHERE event_type='calendar.household.updated'")
            .query { rs, _ -> listOf(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4)) }.single()
        assertThat(row[0]).isEqualTo(partner.user.id.toString())
        assertThat(row[1]).isEqualTo(owner.user.id.toString())
        assertThat(row[2]).isNotBlank()
        assertThat(row[3]).isEqualTo(event.id.toString())
    }

    @Test fun `nonparticipant and nonparticipant owner can see household events but cannot edit or delete`() {
        val event = create(partner.user.id, listOf(other.user.id))
        val view = service.all(owner.user.id).single()
        assertThat(view.canEdit).isFalse()
        assertThat(view.canDelete).isFalse()
        assertThatThrownBy { service.update(owner.user.id, event.id, update(event)) }.isInstanceOf(ForbiddenException::class.java)
        assertThatThrownBy { service.delete(owner.user.id, event.id, 0) }.isInstanceOf(ForbiddenException::class.java)
    }

    @Test fun `stale concurrent edits and deletion are rejected without overwriting newer content`() {
        val event = create()
        service.update(partner.user.id, event.id, update(event))
        assertThatThrownBy { service.update(owner.user.id, event.id, update(event, "Stale write")) }
            .isInstanceOf(HouseholdCalendarFailure::class.java).hasMessage("HOUSEHOLD_CALENDAR_CONFLICT")
        assertThatThrownBy { service.delete(owner.user.id, event.id, 0) }.hasMessage("HOUSEHOLD_CALENDAR_CONFLICT")
        assertThat(service.all(owner.user.id).single().title).isEqualTo("Changed together")
    }

    @Test fun `simultaneous partner edits have one winner and one conflict with one committed audit`() {
        val event = create()
        val gate = java.util.concurrent.CountDownLatch(1)
        val executor = java.util.concurrent.Executors.newFixedThreadPool(2)
        try {
            val attempts = listOf(owner.user.id, partner.user.id).map { actor ->
                executor.submit<String> {
                    gate.await()
                    try { service.update(actor, event.id, update(event, "Edit by $actor")); "saved" }
                    catch (error: HouseholdCalendarFailure) { error.code }
                }
            }
            gate.countDown()
            assertThat(attempts.map { it.get(20, java.util.concurrent.TimeUnit.SECONDS) })
                .containsExactlyInAnyOrder("saved", "HOUSEHOLD_CALENDAR_CONFLICT")
            assertThat(service.all(owner.user.id).single().revision).isEqualTo(1)
            assertThat(jdbc.sql("SELECT count(*) FROM activity_event WHERE event_type='calendar.household.updated'")
                .query(Long::class.java).single()).isEqualTo(1)
        } finally { executor.shutdownNow() }
    }

    @Test fun `revocation deactivation and suspended space prevent subsequent mutations`() {
        val event = create()
        val reader = rbac.createRole(owner.user.id, RoleRequest("calendar-revoked", "No calendar access", setOf("devices:read")))
        rbac.assignRoles(owner.user.id, partner.user.id, setOf(reader.id))
        assertThatThrownBy { service.update(partner.user.id, event.id, update(event)) }.isInstanceOf(ForbiddenException::class.java)
        rbac.deactivate(owner.user.id, other.user.id, false)
        assertThat(service.members(owner.user.id).map { it.id }).doesNotContain(partner.user.id, other.user.id)
        assertThatThrownBy { create(participants = listOf(other.user.id)) }.hasMessage("HOUSEHOLD_CALENDAR_INVALID")
        jdbc.sql("UPDATE kyrion_space SET status='SUSPENDED' WHERE id=:space").param("space", owner.user.id).update()
        assertThatThrownBy { service.all(owner.user.id) }.isInstanceOf(ForbiddenException::class.java)
    }

    @Test fun `foreign household cannot read mutate or be selected and database enforces participant space`() {
        val event = create()
        val foreign = UUID.randomUUID()
        jdbc.sql("INSERT INTO user_account(id,username,password_hash) VALUES(:id,'other-household',:hash)")
            .param("id", foreign).param("hash", hashing.hash(password)).update()
        rbac.initializeUser(foreign, foreign, true)
        assertThat(service.all(foreign)).isEmpty()
        assertThatThrownBy { service.update(foreign, event.id, update(event)) }.hasMessage("HOUSEHOLD_CALENDAR_NOT_FOUND")
        assertThatThrownBy { service.delete(foreign, event.id, 0) }.hasMessage("HOUSEHOLD_CALENDAR_NOT_FOUND")
        assertThatThrownBy { create(participants = listOf(foreign)) }.hasMessage("HOUSEHOLD_CALENDAR_INVALID")
        assertThatThrownBy {
            jdbc.sql("INSERT INTO household_calendar_participant(event_id,space_id,user_id) VALUES(:event,:space,:user)")
                .param("event", event.id).param("space", owner.user.id).param("user", foreign).update()
        }.isInstanceOf(org.springframework.dao.DataIntegrityViolationException::class.java)
    }

    @Test fun `business remains blocked and legacy local events are preserved`() {
        jdbc.sql("INSERT INTO local_calendar_event(id,owner_id,title,starts_at,ends_at,time_zone,content_fingerprint,sync_to_google,created_at,updated_at) VALUES(:id,:owner,'Legacy',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP+INTERVAL '1 hour','UTC','legacy-fingerprint',FALSE,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)")
            .param("id", UUID.randomUUID()).param("owner", owner.user.id).update()
        create()
        assertThat(jdbc.sql("SELECT count(*) FROM local_calendar_event").query(Long::class.java).single()).isEqualTo(1)
        jdbc.sql("UPDATE kyrion_space SET type='BUSINESS' WHERE id=:space").param("space", owner.user.id).update()
        assertThatThrownBy { service.members(owner.user.id) }.isInstanceOf(ForbiddenException::class.java)
        assertThatThrownBy { create() }.isInstanceOf(ForbiddenException::class.java)
    }

    @Test fun `audit failure rolls back event and participant writes`() {
        jdbc.sql("ALTER TABLE activity_event ADD CONSTRAINT household_test_audit_failure CHECK(event_type<>'calendar.household.created') NOT VALID").update()
        try {
            assertThatThrownBy { create() }.isInstanceOf(org.springframework.dao.DataIntegrityViolationException::class.java)
            assertThat(jdbc.sql("SELECT count(*) FROM household_calendar_event").query(Long::class.java).single()).isZero()
            assertThat(jdbc.sql("SELECT count(*) FROM household_calendar_participant").query(Long::class.java).single()).isZero()
        } finally { jdbc.sql("ALTER TABLE activity_event DROP CONSTRAINT household_test_audit_failure").update() }
    }

    @Test fun `HTTP rejects forged identity provider fields null participants and missing or fractional revisions`() {
        val event = create()
        val valid = """{"title":"HTTP edit","startsAt":"2026-11-10T10:00:00Z","endsAt":"2026-11-10T11:00:00Z","timeZone":"Europe/Zurich","revision":0}"""
        for (body in listOf(valid.replace("\"revision\":0", "\"revision\":0,\"actorId\":\"${owner.user.id}\""),
                valid.replace("\"revision\":0", "\"revision\":0.1"), valid.replace(",\"revision\":0", ""),
                valid.replace("\"revision\":0", "\"revision\":0,\"participantIds\":[]"),
                valid.replace("\"revision\":0", "\"revision\":0,\"syncToGoogle\":true"),
                valid.replace("\"title\":\"HTTP edit\"", "\"title\":123"),
                valid.replace("\"revision\":0", "\"revision\":\"0\""))) {
            mvc.perform(put("/v1/calendar/household-events/${event.id}").header("Authorization", "Bearer ${partner.session.rawToken}")
                .contentType("application/json").content(body)).andExpect(status().isBadRequest)
                .andExpect(jsonPath("$.code").value("HOUSEHOLD_CALENDAR_INVALID"))
        }
        val createBody = valid.replace(",\"revision\":0", ",\"participantIds\":[null]")
        mvc.perform(post("/v1/calendar/household-events").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType("application/json").content(createBody)).andExpect(status().isBadRequest)
        val validCreate = valid.replace(",\"revision\":0", ",\"participantIds\":[\"${partner.user.id}\"]")
        mvc.perform(post("/v1/calendar/household-events").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType("application/json").content(validCreate)).andExpect(status().isCreated)
            .andExpect(jsonPath("$.createdBy").value(owner.user.id.toString()))
            .andExpect(jsonPath("$.participantIds.length()").value(2))
        mvc.perform(put("/v1/calendar/household-events/${event.id}").header("Authorization", "Bearer ${partner.session.rawToken}")
            .contentType("application/json").content(valid)).andExpect(status().isOk)
            .andExpect(header().string("Cache-Control", "no-store"))
            .andExpect(jsonPath("$.revision").value(1)).andExpect(jsonPath("$.title").value("HTTP edit"))
        mvc.perform(get("/v1/calendar/household-events")).andExpect(status().isUnauthorized)
        mvc.perform(delete("/v1/calendar/household-events/${event.id}").header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isBadRequest).andExpect(jsonPath("$.code").value("HOUSEHOLD_CALENDAR_INVALID"))
        mvc.perform(put("/v1/calendar/household-events/not-a-uuid").header("Authorization", "Bearer ${partner.session.rawToken}")
            .contentType("application/json").content(valid)).andExpect(status().isBadRequest)
            .andExpect(jsonPath("$.code").value("HOUSEHOLD_CALENDAR_INVALID"))
    }

    @Test fun `range and duplicate participant validation leave no event behind`() {
        assertThatThrownBy { create(participants = listOf(partner.user.id, partner.user.id)) }.hasMessage("HOUSEHOLD_CALENDAR_INVALID")
        assertThatThrownBy { service.all(owner.user.id, start, start.minusSeconds(1)) }.hasMessage("HOUSEHOLD_CALENDAR_INVALID")
        assertThatThrownBy { service.create(owner.user.id, HouseholdEventCreate("bad", start, start, "UTC")) }.hasMessage("HOUSEHOLD_CALENDAR_INVALID")
        assertThatThrownBy { service.all(owner.user.id, start, start.plus(Duration.ofDays(400)).plusSeconds(1)) }.hasMessage("HOUSEHOLD_CALENDAR_INVALID")
        assertThatThrownBy { service.create(owner.user.id, HouseholdEventCreate("bad", start, Instant.parse("+10000-01-01T00:00:00Z"), "UTC")) }.hasMessage("HOUSEHOLD_CALENDAR_INVALID")
        create()
        assertThat(service.all(owner.user.id, start.plusSeconds(7200), start.plusSeconds(10800))).isEmpty()
        assertThat(service.all(owner.user.id, start, start.plusSeconds(3600))).hasSize(1)
    }

    companion object {
        private const val password = "secure-household-calendar-password"
        private val secret = SessionTokenService().create().rawToken
        private val temp = Files.createTempDirectory("kyrion-household-test-")
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
