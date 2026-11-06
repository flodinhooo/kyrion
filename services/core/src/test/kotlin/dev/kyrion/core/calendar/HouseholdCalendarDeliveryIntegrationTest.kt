package dev.kyrion.core.calendar

import dev.kyrion.core.ai.AiTestGatewayConfiguration
import dev.kyrion.core.integration.*
import dev.kyrion.core.security.*
import org.assertj.core.api.Assertions.*
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.test.context.TestConfiguration
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc
import org.springframework.context.annotation.Bean
import org.springframework.context.annotation.Import
import org.springframework.context.annotation.Primary
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
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

@Testcontainers @SpringBootTest @AutoConfigureMockMvc
@Import(AiTestGatewayConfiguration::class, HouseholdCalendarDeliveryIntegrationTest.ProviderConfiguration::class)
class HouseholdCalendarDeliveryIntegrationTest @Autowired constructor(
    private val jdbc: JdbcClient, private val auth: LocalAuthenticationService, private val hashing: PasswordHashingService,
    private val rbac: RbacService, private val household: HouseholdCalendarService, private val service: HouseholdCalendarDelivery,
    private val google: GoogleIntegrationService, private val fake: DeliveryGoogleFake, private val mvc: MockMvc,
    private val deliveries: HouseholdDeliveryRepository,
    private val copyLinks: HouseholdCopyLinksService,
) {
    private lateinit var owner: AuthenticatedOwner
    private lateinit var partner: AuthenticatedOwner
    private val start = Instant.parse("2026-11-12T10:00:00Z")
    @BeforeEach fun setup() {
        fake.reset()
        jdbc.sql("TRUNCATE user_account,activity_event,activity_integrity_chain CASCADE").update()
        jdbc.sql("UPDATE installation_bootstrap_state SET initialized=FALSE").update()
        owner = auth.setup("delivery-owner", password, secret)
        val id = UUID.randomUUID()
        jdbc.sql("INSERT INTO user_account(id,username,password_hash,workspace_owner_id) VALUES(:id,'delivery-partner',:hash,:space)")
            .param("id", id).param("hash", hashing.hash(password)).param("space", owner.user.id).update()
        rbac.initializeUser(id, owner.user.id, false)
        val role = rbac.createRole(owner.user.id, RoleRequest("delivery-calendar", "Calendar member", setOf("calendar:read", "calendar:create", "calendar:update", "calendar:delete")))
        rbac.assignRoles(owner.user.id, id, setOf(role.id))
        partner = auth.login("delivery-partner", password)
        connect(owner); connect(partner)
    }
    private fun connect(actor: AuthenticatedOwner) {
        val url = java.net.URI(google.authorize(actor.user.id).authorizationUrl)
        val state = url.rawQuery.split('&').first { it.startsWith("state=") }.substringAfter('=')
        google.complete(actor.user.id, actor.user.username, state)
    }
    private fun grant(actor: AuthenticatedOwner = partner, calendar: String? = "delivery-calendar") =
        service.change(actor.user.id, HouseholdDestinationChange(calendar, service.setting(actor.user.id).revision))
    private fun event(actor: AuthenticatedOwner = owner, participants: List<UUID> = listOf(partner.user.id)) = household.create(actor.user.id,
        HouseholdEventCreate("Family appointment", start, start.plusSeconds(3600), "Europe/Zurich", "Shared description", participants))
    private fun send(event: HouseholdCalendarEvent, target: HouseholdDestinationSetting, actor: AuthenticatedOwner = owner) =
        service.deliver(actor.user.id, event.id, HouseholdDeliveryRequest(target.id!!, event.revision))
    private fun edit(event: HouseholdCalendarEvent) = household.update(partner.user.id, event.id,
        HouseholdEventUpdate("Edited together", event.startsAt.plusSeconds(60), event.endsAt.plusSeconds(60), event.timeZone, event.revision, "New description"))

    @Test fun `no implicit destination and consent remains personal distinct from read disclosure`() {
        assertThat(service.setting(partner.user.id).enabled).isFalse()
        val event = event()
        assertThat(service.view(owner.user.id, event.id).targets).allSatisfy { assertThat(it.targetId).isNull() }
        val partnerGrant = grant()
        assertThat(service.setting(owner.user.id).enabled).isFalse()
        assertThat(service.view(owner.user.id, event.id).targets.first { it.userId == partner.user.id }.targetId).isEqualTo(partnerGrant.id)
        assertThat(jdbc.sql("SELECT count(*) FROM personal_calendar_disclosure").query(Long::class.java).single()).isZero()
        assertThat(fake.writes).isZero()
    }
    @Test fun `selected recipients receive one canonical copy with actual editor audit`() {
        val event = event(); val first = grant(owner); val second = grant()
        assertThat(send(event, first, partner).state).isEqualTo("SYNCED")
        assertThat(send(event, second, partner).state).isEqualTo("SYNCED")
        assertThat(fake.remote).hasSize(2)
        assertThat(fake.writes).isEqualTo(2)
        assertThat(household.all(owner.user.id).single().id).isEqualTo(event.id)
        val actors = jdbc.sql("SELECT actor_id FROM activity_event WHERE event_type='calendar.delivery.attempt' AND status='SUCCEEDED'").query(String::class.java).list()
        assertThat(actors).containsOnly(partner.user.id.toString())
        assertThat(service.view(owner.user.id, event.id).items).allSatisfy { assertThat(it.deliveredRevision).isEqualTo(0) }
    }
    @Test fun `joint edit does not write automatically and selected republish updates same remote copy`() {
        val initial = event(); val target = grant(); send(initial, target)
        val updated = edit(initial)
        assertThat(fake.writes).isEqualTo(1)
        assertThat(service.view(owner.user.id, updated.id).items.single().state).isEqualTo("OUTDATED")
        assertThat(send(updated, target, partner).state).isEqualTo("SYNCED")
        assertThat(fake.remote).hasSize(1)
        assertThat(fake.writes).isEqualTo(2)
        assertThat(fake.remote.values.single().summary).isEqualTo("Edited together")
        send(updated, target)
        assertThat(fake.writes).isEqualTo(2)
    }
    @Test fun `external edit and ETag mismatch never overwrite personal changes`() {
        val initial = event(); val target = grant(); send(initial, target)
        fake.remote.replaceAll { _, value -> value.copy(summary = "External change", etag = "external-v2") }
        val updated = edit(initial)
        assertThat(send(updated, target).state).isEqualTo("CONFLICT")
        assertThat(fake.remote.values.single().summary).isEqualTo("External change")
        assertThat(fake.writes).isEqualTo(1)
    }
    @Test fun `lost insert response is recovered from exact marker and content without duplicate write`() {
        val event = event(); val target = grant()
        fake.failAfterCreate = true
        assertThat(send(event, target).state).isEqualTo("NEEDS_REVIEW")
        assertThat(fake.remote).hasSize(1)
        fake.failAfterCreate = false
        assertThat(send(event, target).state).isEqualTo("SYNCED")
        assertThat(fake.writes).isEqualTo(1)
    }
    @Test fun `uncertain insert with missing copy is not silently recreated`() {
        val event = event(); val target = grant()
        fake.failBeforeCreate = true
        assertThat(send(event, target).state).isEqualTo("NEEDS_REVIEW")
        fake.failBeforeCreate = false
        assertThat(send(event, target).state).isEqualTo("CONFLICT")
        assertThat(fake.createCalls).isEqualTo(1)
        assertThat(fake.remote).isEmpty()
    }
    @Test fun `revocation between remote read and write causes zero dispatch`() {
        val event = event(); val target = grant()
        fake.onGet = { grant(calendar = null) }
        assertThat(send(event, target).state).isEqualTo("BLOCKED")
        assertThat(fake.writes).isZero()
        assertThat(fake.createCalls).isZero()
        val renewed = grant()
        assertThat(send(event, renewed).state).isEqualTo("SYNCED")
        assertThat(fake.remote).hasSize(1)
    }
    @Test fun `in flight revocation records review and never claims synchronized success`() {
        val event = event(); val target = grant()
        fake.onCreate = { grant(calendar = null) }
        val outcome = send(event, target)
        assertThat(outcome.state).isIn("NEEDS_REVIEW", "BLOCKED")
        assertThat(outcome.deliveredRevision).isNull()
        assertThat(fake.writes).isEqualTo(1)
        assertThatThrownBy { send(event, target) }.hasMessage("CALENDAR_DELIVERY_UNAVAILABLE")
        assertThat(fake.writes).isEqualTo(1)
    }
    @Test fun `provider read failure is independent per target and retry is explicit`() {
        val event = event(); val first = grant(owner); val second = grant()
        fake.getFailureToken = owner.user.username
        assertThat(send(event, first).state).isEqualTo("ERROR")
        assertThat(send(event, second).state).isEqualTo("SYNCED")
        assertThat(fake.writes).isEqualTo(1)
        fake.getFailureToken = null
        assertThat(send(event, first).state).isEqualTo("SYNCED")
        assertThat(fake.writes).isEqualTo(2)
    }
    @Test fun `definitively denied insert remains retryable after provider permission repair`() {
        val event = event(); val target = grant()
        fake.createFailure = 403
        assertThat(send(event, target).state).isEqualTo("ERROR")
        assertThat(fake.writes).isZero()
        fake.createFailure = null
        assertThat(send(event, target).state).isEqualTo("SYNCED")
        assertThat(fake.remote).hasSize(1)
    }
    @Test fun `token refresh retry revalidates withdrawn consent before another provider call`() {
        val event = event(); val target = grant()
        fake.createFailure = 401
        fake.onCreate = { grant(calendar = null) }
        assertThat(send(event, target).state).isNotEqualTo("SYNCED")
        assertThat(fake.createCalls).isEqualTo(1)
        assertThat(fake.writes).isZero()
    }
    @Test fun `a nonparticipant owner cannot publish and a revoked recipient role cannot receive`() {
        val target = grant()
        val personal = event(partner, emptyList())
        assertThatThrownBy { send(personal, target) }.isInstanceOf(ForbiddenException::class.java)
        val joint = event()
        val role = rbac.createRole(owner.user.id, RoleRequest("delivery-read-only", "Read only", setOf("calendar:read")))
        rbac.assignRoles(owner.user.id, partner.user.id, setOf(role.id))
        assertThat(service.view(owner.user.id, joint.id).targets.first { it.userId == partner.user.id }.targetId).isNull()
        assertThatThrownBy { send(joint, target) }.isInstanceOf(ForbiddenException::class.java)
        assertThat(fake.writes).isZero()
    }
    @Test fun `disconnect and new connection do not inherit destination consent`() {
        val event = event(); val target = grant()
        jdbc.sql("DELETE FROM integration_connection WHERE owner_id=:user AND provider='google'").param("user", partner.user.id).update()
        connect(partner)
        assertThat(service.setting(partner.user.id).enabled).isFalse()
        assertThatThrownBy { send(event, target) }.hasMessage("CALENDAR_DELIVERY_UNAVAILABLE")
        assertThat(fake.writes).isZero()
    }
    @Test fun `same destination reenable reuses copy and new destination retains previous copy`() {
        val event = event(); val first = grant(); send(event, first)
        grant(calendar = null)
        val renewed = grant(); assertThat(renewed.id).isNotEqualTo(first.id)
        send(event, renewed)
        assertThat(fake.writes).isEqualTo(1)
        val changed = grant(calendar = "delivery-alternative"); send(event, changed)
        assertThat(fake.remote).hasSize(2)
        assertThat(service.view(owner.user.id, event.id).items.map { it.state }).containsExactlyInAnyOrder("BLOCKED", "SYNCED")
    }
    @Test fun `concurrent delivery has one reserved attempt and deletion is blocked while running`() {
        val event = event(); val target = grant()
        val entered = CountDownLatch(1); val release = CountDownLatch(1)
        fake.onGet = { entered.countDown(); check(release.await(20, TimeUnit.SECONDS)) }
        val executor = java.util.concurrent.Executors.newSingleThreadExecutor()
        try {
            val running = executor.submit<HouseholdDeliveryView> { send(event, target) }
            check(entered.await(20, TimeUnit.SECONDS))
            assertThatThrownBy { send(event, target) }.hasMessage("CALENDAR_DELIVERY_BUSY")
            assertThatThrownBy { household.delete(owner.user.id, event.id, event.revision, true) }.hasMessage("CALENDAR_DELIVERY_BUSY")
            release.countDown()
            assertThat(running.get(20, TimeUnit.SECONDS).state).isEqualTo("SYNCED")
            assertThat(fake.writes).isEqualTo(1)
        } finally { release.countDown(); executor.shutdownNow() }
    }
    @Test fun `deleted confirmed copy and recurring conversion are conflicts without recreation`() {
        val event = event(); val target = grant(); send(event, target)
        val key = fake.remote.keys.single(); val remote = fake.remote.getValue(key)
        fake.remote[key] = remote.copy(recurring = true)
        assertThat(send(event, target).state).isEqualTo("CONFLICT")
        fake.remote.clear()
        assertThat(send(event, target).state).isEqualTo("CONFLICT")
        assertThat(fake.writes).isEqualTo(1)
    }
    @Test fun `native deletion requires retention acknowledgement and leaves provider copy alone`() {
        val event = event(); val target = grant(); send(event, target)
        assertThatThrownBy { household.delete(owner.user.id, event.id, event.revision) }.hasMessage("CALENDAR_DELIVERY_RETENTION_REQUIRED")
        household.delete(owner.user.id, event.id, event.revision, true)
        assertThat(household.all(owner.user.id)).isEmpty()
        assertThat(fake.remote).hasSize(1)
        assertThat(jdbc.sql("SELECT count(*) FROM activity_event WHERE event_type='calendar.household.copy_retained'").query(Long::class.java).single()).isEqualTo(1)
    }
    @Test fun `failed proposal audit rolls back reservation and dispatches nothing`() {
        val event = event(); val target = grant()
        jdbc.sql("ALTER TABLE activity_event ADD CONSTRAINT delivery_audit_failure CHECK(event_type<>'calendar.delivery.attempt') NOT VALID").update()
        try {
            assertThatThrownBy { send(event, target) }.isInstanceOf(org.springframework.dao.DataIntegrityViolationException::class.java)
            assertThat(fake.createCalls).isZero()
            assertThat(deliveries.rows(owner.user.id, event.id)).isEmpty()
        } finally { jdbc.sql("ALTER TABLE activity_event DROP CONSTRAINT delivery_audit_failure").update() }
    }
    @Test fun `HTTP validates explicit targets revision identity and does not expose provider metadata`() {
        val event = event(); val target = grant()
        val url = "/v1/calendar/household-events/${event.id}/deliveries"
        for (body in listOf("""{"targetId":"${target.id}","revision":0,"actorId":"${owner.user.id}"}""",
                """{"targetId":"${target.id}","revision":"0"}""", """{"targetId":"${target.id}","revision":0.5}""")) {
            mvc.perform(post(url).header("Authorization", "Bearer ${owner.session.rawToken}").contentType("application/json").content(body))
                .andExpect(status().isBadRequest).andExpect(jsonPath("$.code").value("CALENDAR_DELIVERY_INVALID"))
        }
        mvc.perform(post(url).header("Authorization", "Bearer ${owner.session.rawToken}").contentType("application/json")
            .content("""{"targetId":"${target.id}","revision":0}"""))
            .andExpect(status().isOk).andExpect(jsonPath("$.state").value("SYNCED"))
            .andExpect(header().string("Cache-Control", "no-store"))
            .andExpect(content().string(org.hamcrest.Matchers.not(org.hamcrest.Matchers.containsString("delivery-calendar"))))
            .andExpect(jsonPath("$.etag").doesNotExist()).andExpect(jsonPath("$.remoteId").doesNotExist())
    }
    @Test fun `lost patch response recovers matching desired content without a second patch`() {
        val initial = event(); val target = grant(); send(initial, target)
        val changed = edit(initial)
        fake.failAfterPatch = true
        assertThat(send(changed, target).state).isEqualTo("NEEDS_REVIEW")
        fake.failAfterPatch = false
        assertThat(send(changed, target).state).isEqualTo("SYNCED")
        assertThat(fake.writes).isEqualTo(2)
    }
    @Test fun `native edit during provider write records review rather than newer revision success`() {
        val initial = event(); val target = grant()
        fake.onCreate = { edit(initial) }
        assertThat(send(initial, target).state).isEqualTo("NEEDS_REVIEW")
        assertThat(service.view(owner.user.id, initial.id).items.single().deliveredRevision).isNull()
        assertThat(fake.remote.values.single().summary).isEqualTo(initial.title)
        assertThat(household.all(owner.user.id).single().title).isEqualTo("Edited together")
    }
    @Test fun `actual foreign space grant and Business transition cannot authorize provider access`() {
        val initial = event(); val own = grant()
        val foreign = UUID.randomUUID()
        jdbc.sql("INSERT INTO user_account(id,username,password_hash) VALUES(:id,'delivery-foreign',:hash)")
            .param("id", foreign).param("hash", hashing.hash(password)).update()
        rbac.initializeUser(foreign, foreign, true)
        val url = java.net.URI(google.authorize(foreign).authorizationUrl)
        val state = url.rawQuery.split('&').first { it.startsWith("state=") }.substringAfter('=')
        google.complete(foreign, "delivery-foreign", state)
        val grant = service.change(foreign, HouseholdDestinationChange("delivery-calendar", 0))
        assertThatThrownBy { service.deliver(owner.user.id, initial.id, HouseholdDeliveryRequest(grant.id!!, 0)) }.hasMessage("CALENDAR_DELIVERY_UNAVAILABLE")
        assertThatThrownBy { service.view(foreign, initial.id) }.hasMessage("CALENDAR_DELIVERY_UNAVAILABLE")
        jdbc.sql("UPDATE kyrion_space SET type='BUSINESS' WHERE id=:space").param("space", owner.user.id).update()
        assertThatThrownBy { send(initial, own) }.isInstanceOf(ForbiddenException::class.java)
        assertThat(fake.writes).isZero()
    }
    @Test fun `stale event and foreign destination fail before provider access`() {
        val initial = event(); val target = grant(); edit(initial)
        assertThatThrownBy { send(initial, target) }.hasMessage("CALENDAR_DELIVERY_STALE")
        assertThatThrownBy { service.deliver(owner.user.id, initial.id, HouseholdDeliveryRequest(UUID.randomUUID(), 1)) }
            .hasMessage("CALENDAR_DELIVERY_UNAVAILABLE")
        assertThat(fake.createCalls).isZero()
    }
    @Test fun `expired lease can recover but superseded attempt cannot finalize newer record`() {
        val event = event(); val target = grant(); send(event, target)
        val old = deliveries.rows(owner.user.id, event.id).single()
        jdbc.sql("UPDATE household_calendar_delivery SET state='RUNNING',lease_until=TIMESTAMPTZ '2000-01-01 00:00:00+00' WHERE id=:id").param("id", old.id).update()
        assertThat(send(event, target).state).isEqualTo("SYNCED")
        assertThat(deliveries.finish(owner.user.id, old, "ERROR", "STALE", null, null)).isFalse()
        assertThat(fake.writes).isEqualTo(1)
    }
    @Test fun `copy links belong only to the authenticated credential owner and selected actual calendar`() {
        val event = event(); val first = grant(owner); val second = grant()
        send(event, first); send(event, second)
        val mine = copyLinks.links(owner.user.id, "delivery-calendar").single()
        val theirs = copyLinks.links(partner.user.id, "delivery-calendar").single()
        assertThat(mine.eventId).isEqualTo(event.id)
        assertThat(theirs.eventId).isEqualTo(event.id)
        assertThat(mine.remoteId).isNotEqualTo(theirs.remoteId)
        assertThat(copyLinks.links(partner.user.id, "delivery-alternative")).isEmpty()
        assertThat(copyLinks.links(partner.user.id, "primary")).isEmpty()
    }
    @Test fun `copy links require confirmed current revision and vanish for outdated or conflicting attempts`() {
        val initial = event(); val target = grant(); send(initial, target)
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar")).hasSize(1)
        val changed = edit(initial)
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar")).isEmpty()
        send(changed, target)
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar").single().revision).isEqualTo(1)
        fake.remote.replaceAll { _, value -> value.copy(summary = "External", etag = "external") }
        assertThat(send(changed, target).state).isEqualTo("CONFLICT")
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar")).isEmpty()
    }
    @Test fun `revocation and changed destination retain independent copies without suppression links`() {
        val event = event(); val target = grant(); send(event, target)
        grant(calendar = null)
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar")).isEmpty()
        val next = grant(calendar = "delivery-alternative"); send(event, next)
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar")).isEmpty()
        assertThat(copyLinks.links(partner.user.id, "delivery-alternative")).hasSize(1)
        assertThat(fake.remote).hasSize(2)
    }
    @Test fun `read only role or lost connection preserves calendar copy visibility by returning no links`() {
        val event = event(); val target = grant(); send(event, target)
        val role = rbac.createRole(owner.user.id, RoleRequest("copy-read-only", "Read only", setOf("calendar:read")))
        rbac.assignRoles(owner.user.id, partner.user.id, setOf(role.id))
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar")).isEmpty()
        val original = rbac.roles(owner.user.id).first { it.key == "delivery-calendar" }
        rbac.assignRoles(owner.user.id, partner.user.id, setOf(original.id))
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar")).hasSize(1)
        jdbc.sql("DELETE FROM integration_connection WHERE owner_id=:user AND provider='google'").param("user", partner.user.id).update()
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar")).isEmpty()
    }
    @Test fun `copy links reject disabled actors and Business spaces`() {
        val event = event(); val target = grant(); send(event, target)
        rbac.deactivate(owner.user.id, partner.user.id, false)
        assertThatThrownBy { copyLinks.links(partner.user.id, "delivery-calendar") }.isInstanceOf(ForbiddenException::class.java)
        jdbc.sql("UPDATE kyrion_space SET type='BUSINESS' WHERE id=:space").param("space", owner.user.id).update()
        assertThatThrownBy { copyLinks.links(owner.user.id, "delivery-calendar") }.isInstanceOf(ForbiddenException::class.java)
    }
    @Test fun `copy link range is bounded and original provider identifiers never enter another owners response`() {
        val event = event(); val target = grant(); send(event, target)
        assertThat(copyLinks.links(partner.user.id, "delivery-calendar", start.plusSeconds(7200), start.plusSeconds(10800))).isEmpty()
        assertThatThrownBy { copyLinks.links(partner.user.id, "delivery-calendar", start, null) }.hasMessage("HOUSEHOLD_COPY_LINKS_INVALID")
        assertThatThrownBy { copyLinks.links(partner.user.id, "delivery-calendar", start, start.plus(Duration.ofDays(401))) }.hasMessage("HOUSEHOLD_COPY_LINKS_INVALID")
        mvc.perform(get("/v1/calendar/household-copy-links").param("calendarId", "delivery-calendar").param("userId", partner.user.id.toString())
            .header("Authorization", "Bearer ${owner.session.rawToken}")).andExpect(status().isOk)
            .andExpect(content().json("[]")).andExpect(header().string("Cache-Control", "no-store"))
        mvc.perform(get("/v1/calendar/household-copy-links").param("calendarId", "delivery-calendar")).andExpect(status().isUnauthorized)
        mvc.perform(get("/v1/calendar/household-copy-links").header("Authorization", "Bearer ${partner.session.rawToken}"))
            .andExpect(status().isBadRequest).andExpect(jsonPath("$.code").value("HOUSEHOLD_COPY_LINKS_INVALID"))
    }
    @TestConfiguration(proxyBeanMethods = false)
    class ProviderConfiguration { @Bean @Primary fun deliveryGoogleFake() = DeliveryGoogleFake() }
    companion object {
        private const val password = "secure-calendar-delivery-password"
        private val secret = SessionTokenService().create().rawToken
        private val temp = Files.createTempDirectory("kyrion-delivery-test-")
        private val bootstrap = temp.resolve("bootstrap").also { Files.writeString(it, secret) }
        private val key = temp.resolve("key").also { Files.write(it, ByteArray(32) { (it + 1).toByte() }) }
        @Container @JvmStatic val postgres = PostgreSQLContainer("postgres:17-alpine").withStartupTimeout(Duration.ofMinutes(3))
        @DynamicPropertySource @JvmStatic fun properties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url", postgres::getJdbcUrl); registry.add("spring.datasource.username", postgres::getUsername); registry.add("spring.datasource.password", postgres::getPassword)
            registry.add("kyrion.security.bootstrap-secret-file") { bootstrap.toString() }; registry.add("kyrion.audit.integrity-key-file") { key.toString() }; registry.add("kyrion.credentials.key-file") { key.toString() }
            registry.add("kyrion.knowledge.root") { temp.resolve("documents").toString() }; registry.add("kyrion.knowledge.worker-enabled") { "false" }
            registry.add("kyrion.calendar.sync.scheduler-enabled") { "false" }; registry.add("kyrion.home-assistant.refresh-enabled") { "false" }
            registry.add("kyrion.google.client-id") { "test-client" }; registry.add("kyrion.google.client-secret") { "test-secret" }; registry.add("kyrion.google.redirect-uri") { "http://localhost.test/callback" }
        }
    }
}

class DeliveryGoogleFake : GoogleOAuthClient {
    val remote = ConcurrentHashMap<String, GoogleCalendarEvent>()
    var writes = 0; var createCalls = 0
    var failBeforeCreate = false; var failAfterCreate = false; var getFailureToken: String? = null
    var createFailure: Int? = null
    var failAfterPatch = false
    var onGet: (() -> Unit)? = null; var onCreate: (() -> Unit)? = null
    fun reset() { remote.clear(); writes = 0; createCalls = 0; failBeforeCreate = false; failAfterCreate = false; getFailureToken = null; onGet = null; onCreate = null; createFailure = null; failAfterPatch = false }
    override fun exchange(code: String, redirectUri: String, clientId: String, clientSecret: String) = GoogleToken(code, "test-refresh-$code", Instant.now().plusSeconds(3600), "$code@example.invalid")
    override fun refresh(refreshToken: String, clientId: String, clientSecret: String, accountName: String) = GoogleToken(accountName.substringBefore('@'), refreshToken, Instant.now().plusSeconds(3600), accountName)
    override fun revoke(token: String) = Unit
    override fun events(accessToken: String) = GoogleCalendarEvents(emptyList())
    override fun calendars(accessToken: String) = GoogleCalendars(listOf(GoogleCalendar("delivery-calendar", "Personal destination", "UTC", "owner"), GoogleCalendar("delivery-alternative", "Other destination", "UTC", "writer")))
    override fun getEvent(accessToken: String, calendarId: String, eventId: String): GoogleCalendarEvent {
        val hook = onGet; onGet = null; hook?.invoke()
        if (accessToken == getFailureToken) throw GoogleProviderException(503)
        return remote["$accessToken:$calendarId:$eventId"] ?: throw GoogleProviderException(404)
    }
    override fun createEvent(accessToken: String, body: GoogleCalendarEventRequest): GoogleCalendarEvent {
        createCalls++
        if (failBeforeCreate) throw java.io.IOException("Synthetic transport loss")
        val hook = onCreate; onCreate = null; hook?.invoke()
        createFailure?.let { throw GoogleProviderException(it) }
        val id = body.id!!; val key = "$accessToken:${body.calendarId}:$id"
        if (remote.containsKey(key)) throw GoogleProviderException(409)
        writes++
        val result = GoogleCalendarEvent(id, body.summary, body.start, body.end, "test-etag-$writes", description = body.description, kyrionId = id)
        remote[key] = result
        if (failAfterCreate) throw java.io.IOException("Synthetic response loss")
        return result
    }
    override fun patchEvent(accessToken: String, eventId: String, body: GoogleCalendarEventRequest, etag: String): GoogleCalendarEvent {
        val key = "$accessToken:${body.calendarId}:$eventId"
        val old = remote[key] ?: throw GoogleProviderException(404)
        if (old.etag != etag) throw GoogleProviderException(412)
        writes++
        val result = old.copy(summary = body.summary, start = body.start, end = body.end, description = body.description, etag = "test-etag-$writes").also { remote[key] = it }
        if (failAfterPatch) throw java.io.IOException("Synthetic patch response loss")
        return result
    }
}
