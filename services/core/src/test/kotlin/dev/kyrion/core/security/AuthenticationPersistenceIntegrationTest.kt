package dev.kyrion.core.security

import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.activity.ActivityCategory
import dev.kyrion.core.activity.ActivityService
import dev.kyrion.core.activity.ActivityStatus
import dev.kyrion.core.conversation.Conversation
import dev.kyrion.core.conversation.ConversationMessage
import dev.kyrion.core.conversation.ConversationRepository
import dev.kyrion.core.conversation.ConversationNotFoundException
import dev.kyrion.core.memory.PersonalMemoryRepository
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.http.MediaType
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.delete
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer
import java.sql.Timestamp
import java.time.Instant
import java.util.UUID
import java.nio.file.Files
import java.nio.file.Path
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.mockito.Mockito.`when`
import org.mockito.Mockito.verify
import dev.kyrion.core.integration.NanoleafGateway
import dev.kyrion.core.integration.NanoleafDeviceState
import dev.kyrion.core.integration.NanoleafIntegrationService

@org.springframework.context.annotation.Import(dev.kyrion.core.ai.AiTestGatewayConfiguration::class)
@Testcontainers
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@AutoConfigureMockMvc
class AuthenticationPersistenceIntegrationTest @Autowired constructor(
    private val authentication: LocalAuthenticationService,
    private val conversations: ConversationRepository,
    private val passwordHashing: PasswordHashingService,
    private val jdbc: JdbcClient,
    private val memories: PersonalMemoryRepository,
    private val mockMvc: MockMvc,
    private val activity: ActivityService,
    private val haReconciler: dev.kyrion.core.integration.HomeAssistantReconciler,
    private val catalog: dev.kyrion.core.capability.DeviceCatalogService,
    private val rooms: dev.kyrion.core.home.RoomRepository,
    private val transactions: org.springframework.transaction.support.TransactionTemplate,
    private val nanoleaf: NanoleafIntegrationService,
    private val rbac: RbacService,
    private val google: dev.kyrion.core.integration.GoogleIntegrationService,
    private val scheduler: org.springframework.scheduling.TaskScheduler,
    private val aiGateway: dev.kyrion.core.ai.AiTestGateway,
    private val aiSettings: dev.kyrion.core.ai.AiSettingsService,
    private val aiUsage: dev.kyrion.core.ai.AiUsageService,
    private val aiOrchestration: dev.kyrion.core.ai.AiOrchestrationService,
) {
    @MockitoBean
    lateinit var nanoleafGateway: NanoleafGateway

    @MockitoBean
    lateinit var googleClient: dev.kyrion.core.integration.GoogleOAuthClient

    @BeforeEach
    fun cleanDatabase() {
        aiGateway.reset()
        jdbc.sql(
            "TRUNCATE TABLE gateway_node, gateway_enrollment, personal_memory, owner_memory_settings, conversation_turn, conversation_context_summary, conversation_message, conversation, auth_session, user_account, activity_event, activity_integrity_chain CASCADE",
        ).update()
        jdbc.sql("UPDATE installation_bootstrap_state SET initialized=FALSE").update()
    }

    @Test
    fun `invited friend controls owner devices while keeping identity and personal data separate`() {
        val owner = authentication.setup("flo", OLD_PASSWORD, setupSecret)
        val invitationResult = mockMvc.perform(post("/v1/auth/invitations")
            .header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isCreated).andReturn()
        val mapper = com.fasterxml.jackson.module.kotlin.jacksonObjectMapper()
        val code = mapper.readTree(invitationResult.response.contentAsString).path("code").asText()
        assertThat(jdbc.sql("SELECT token_hash FROM registration_invitation").query(String::class.java).single())
            .isEqualTo(SessionTokenService().hash(code)).isNotEqualTo(code)
        val registration = mockMvc.perform(post("/v1/auth/register").contentType(MediaType.APPLICATION_JSON)
            .content("""{"username":"Friend","password":"$OTHER_PASSWORD","invitationCode":"$code"}"""))
            .andExpect(status().isCreated).andExpect(jsonPath("$.user.canInvite").value(false)).andReturn()
        val token = mapper.readTree(registration.response.contentAsString).path("sessionToken").asText()
        val friend = authentication.authenticate(token)!!
        assertThat(friend.id).isNotEqualTo(owner.user.id)
        assertThat(friend.resourceOwnerId).isEqualTo(owner.user.id)
        mockMvc.perform(get("/v1/auth/me").header("Authorization", "Bearer $token"))
            .andExpect(status().isOk).andExpect(jsonPath("$.id").value(friend.id.toString()))
        mockMvc.perform(post("/v1/auth/invitations").header("Authorization", "Bearer $token"))
            .andExpect(status().isForbidden)

        mockMvc.perform(post("/v1/home/rooms").header("Authorization", "Bearer $token")
            .contentType(MediaType.APPLICATION_JSON).content("""{"name":"Shared room","roomType":"other"}"""))
            .andExpect(status().isCreated)
        assertThat(rooms.all(owner.user.id).single().name).isEqualTo("Shared room")
        assertThat(rooms.all(friend.id)).isEmpty()
        val roomEvent = activity.recent(owner.user.id, 100).single { it.eventType == "home.room.created" }
        assertThat(roomEvent.actorId).isEqualTo(friend.id.toString())
        assertThat(roomEvent.ownerId).isEqualTo(owner.user.id)

        val host = "192.168.1.41"
        `when`(nanoleafGateway.pair(host)).thenReturn("test-provider-token")
        `when`(nanoleafGateway.state(host, "test-provider-token"))
            .thenReturn(NanoleafDeviceState("Shared lamp", null, null, true, 50))
        val device = nanoleaf.pair(owner.user.id, host, "Shared lamp")
        mockMvc.perform(get("/v1/devices").header("Authorization", "Bearer $token"))
            .andExpect(status().isOk).andExpect(jsonPath("$[0].id").value(device.id.toString()))
        mockMvc.perform(post("/v1/device-commands").header("Authorization", "Bearer $token")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""{"capability":"power.set","selector":{"provider":"nanoleaf","deviceId":"${device.id}"},"arguments":{"on":true}}"""))
            .andExpect(status().isOk).andExpect(jsonPath("$.succeeded").value(1))
        verify(nanoleafGateway).setPower(host, "test-provider-token", true)
        assertThat(activity.recent(owner.user.id, 100).filter { it.eventType == "integration.nanoleaf.power" })
            .allMatch { it.actorId == friend.id.toString() && it.ownerId == owner.user.id }

        val now = Instant.now()
        val conversation = Conversation(UUID.randomUUID(), "Private", now, now, emptyList())
        conversations.replace(owner.user.id, conversation)
        mockMvc.perform(get("/v1/conversations/${conversation.id}").header("Authorization", "Bearer $token"))
            .andExpect(status().isNotFound)
        mockMvc.perform(delete("/v1/auth/sessions/${owner.session.session.id}").header("Authorization", "Bearer $token"))
            .andExpect(status().isNotFound)
        mockMvc.perform(post("/v1/auth/register").contentType(MediaType.APPLICATION_JSON)
            .content("""{"username":"another","password":"$OTHER_PASSWORD","invitationCode":"$code"}"""))
            .andExpect(status().isBadRequest).andExpect(jsonPath("$.code").value("INVITATION_INVALID"))
        mockMvc.perform(get("/v1/devices")).andExpect(status().isUnauthorized)
        assertThat(authentication.authenticate(owner.session.rawToken)).isNotNull()
    }

    @Test
    fun `registration rejects duplicates expired invitations and concurrent redemption atomically`() {
        val owner = authentication.setup("flo", OLD_PASSWORD, setupSecret)
        val invitation = authentication.createInvitation(owner.session.rawToken)
        assertThatThrownBy { authentication.register("FLO", OTHER_PASSWORD, invitation.code) }
            .isInstanceOf(UsernameTakenException::class.java)
        val executor = java.util.concurrent.Executors.newFixedThreadPool(2)
        try {
            val results = executor.invokeAll((1..2).map { number -> java.util.concurrent.Callable {
                runCatching { authentication.register("friend$number", OTHER_PASSWORD, invitation.code) }
            } }).map { it.get() }
            assertThat(results.count { it.isSuccess }).isEqualTo(1)
            assertThat(results.single { it.isFailure }.exceptionOrNull()).isInstanceOf(InvalidInvitationException::class.java)
        } finally { executor.shutdownNow() }
        val expired = authentication.createInvitation(owner.session.rawToken)
        val expiredAt = Instant.now().minusSeconds(1)
        jdbc.sql("UPDATE registration_invitation SET expires_at=:expiresAt WHERE token_hash=:hash")
            .param("expiresAt", Timestamp.from(expiredAt))
            .param("hash", SessionTokenService().hash(expired.code)).update()
        assertThatThrownBy { authentication.register("expired", OTHER_PASSWORD, expired.code) }
            .isInstanceOf(InvalidInvitationException::class.java)
        assertThat(jdbc.sql("SELECT count(*) FROM user_account").query(Int::class.java).single()).isEqualTo(2)
        mockMvc.perform(post("/v1/auth/invitations")).andExpect(status().isUnauthorized)
        mockMvc.perform(post("/v1/auth/register").contentType(MediaType.APPLICATION_JSON)
            .content("""{"username":"bad name","password":"short","invitationCode":"invalid"}"""))
            .andExpect(status().isBadRequest)
    }

    @Test
    fun `HA sync records success and safe failure diagnostics without replacing prior inventory`() {
        val login = authentication.setup("flo", OLD_PASSWORD, setupSecret)
        val owner = login.user.id
        var failure: String? = null
        var snapshots = 0
        val gateway = object : dev.kyrion.core.integration.HomeAssistantGateway {
            override fun snapshot(ownerId: UUID): List<dev.kyrion.core.integration.HomeAssistantDevice> {
                snapshots++
                failure?.let { throw dev.kyrion.core.integration.HomeAssistantException(it) }
                return emptyList()
            }
        }
        val service = dev.kyrion.core.integration.HomeAssistantImportService(
            dev.kyrion.core.integration.HomeAssistantConfiguration("http://192.168.1.20:8123", "test-token", owner.toString()),
            gateway, haReconciler, jdbc, transactions, activity)
        assertThat(service.status(owner).reason).isEqualTo("no_observation")
        val result = service.sync(owner)
        assertThat(result.reason).isNull()
        val success = service.status(owner)
        assertThat(success.status).isEqualTo("healthy")
        assertThat(success.lastSuccessAt).isNotNull()
        assertThat(success.correlationId).isEqualTo(result.correlationId)
        service.refreshIfDue(owner)
        service.refreshIfDue(owner)
        assertThat(snapshots).isEqualTo(1)
        for (code in listOf("authentication_failed", "dependency_unreachable", "invalid_response")) {
            failure = code
            assertThat(service.sync(owner).reason).isEqualTo(code)
            val failed = service.status(owner)
            assertThat(failed.reason).isEqualTo(code)
            assertThat(failed.lastSuccessAt).isEqualTo(success.lastSuccessAt)
        }
        assertThat(service.status(UUID.randomUUID()).reason).isEqualTo("configuration_missing")
        jdbc.sql("UPDATE home_assistant_sync SET attempted_at=attempted_at - INTERVAL '2 minutes' WHERE owner_id=:owner")
            .param("owner", owner).update()
        assertThat(service.status(owner).reason).isEqualTo("stale_observation")
        assertThat(service.status(owner).lastError).isEqualTo("invalid_response")
        failure = null
        service.refreshIfDue(owner)
        assertThat(snapshots).isEqualTo(5)
        assertThat(service.status(owner).status).isEqualTo("healthy")
        assertThat(service.status(owner).lastError).isNull()
        assertThat(activity.recent(owner,100).first { it.correlationId == service.status(owner).correlationId }.actorType).isEqualTo(ActivityActorType.SYSTEM)
        mockMvc.perform(get("/v1/integrations/platform-diagnostics/database").header("Authorization", "Bearer ${login.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$.status").value("healthy"))
    }

    @Test
    fun `HA device import persists identity room state and owner boundaries through HTTP catalog`() {
        val login = authentication.setup("flo", OLD_PASSWORD, setupSecret)
        val owner = login.user.id
        val now = Instant.now()
        val room = rooms.create(owner, dev.kyrion.core.home.Room(UUID.randomUUID(), "Wohnzimmer", now, now))
        val externalId = "a".repeat(32)
        val sensor = dev.kyrion.core.integration.HomeAssistantDevice(externalId, "Shelly H&T", " wohnZIMMER ", "Shelly H&T Gen3",
            dev.kyrion.core.integration.DeviceClass.SENSOR, dev.kyrion.core.capability.DeviceAvailability.ONLINE,
            dev.kyrion.core.capability.DeviceStateView(null, null, null, null, null, temperatureCelsius = 22.0, relativeHumidity = 45.0, measuredAt = now),
            listOf("temperature.read", "humidity.read"))
        haReconciler.reconcile(owner, listOf(sensor))
        val imported = catalog.devices(owner).single()
        assertThat(imported.room?.id).isEqualTo(room.id)
        assertThat(imported.state?.temperatureCelsius).isEqualTo(22.0)
        haReconciler.reconcile(owner, listOf(sensor.copy(name = "Renamed", area = "Wohnzimmer OG",
            availability = dev.kyrion.core.capability.DeviceAvailability.OFFLINE,
            state = sensor.state.copy(temperatureCelsius = null, relativeHumidity = null))))
        val updated = catalog.devices(owner).single()
        assertThat(updated.id).isEqualTo(imported.id)
        assertThat(updated.displayName).isEqualTo("Renamed")
        assertThat(updated.room).isNull()
        assertThat(updated.availability).isEqualTo(dev.kyrion.core.capability.DeviceAvailability.UNKNOWN)
        assertThat(updated.diagnosticReason).isEqualTo("integration.disconnected")
        assertThat(rooms.all(owner)).hasSize(1)
        val another = insertAdditionalOwner("another")
        assertThat(catalog.devices(another)).isEmpty()
        mockMvc.perform(get("/v1/devices").header("Authorization", "Bearer ${login.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$[0].provider").value("home_assistant"))
            .andExpect(jsonPath("$[0].endpointHost").doesNotExist()).andExpect(jsonPath("$[0].externalId").doesNotExist())
        mockMvc.perform(post("/v1/device-commands").header("Authorization", "Bearer ${login.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content("""{"capability":"power.set","selector":{"provider":"home_assistant","deviceId":"${imported.id}"},"arguments":{"on":true}}"""))
            .andExpect(status().isBadRequest).andExpect(jsonPath("$.code").value("DEVICE_CAPABILITY_UNSUPPORTED"))
        mockMvc.perform(post("/v1/integrations/home-assistant/sync")).andExpect(status().isUnauthorized)
        haReconciler.reconcile(owner, emptyList())
        assertThat(catalog.devices(owner).single().availability).isEqualTo(dev.kyrion.core.capability.DeviceAvailability.UNKNOWN)
    }

    @Test
    fun `timeline queries complete owner scoped history and sanitize legacy provider payloads`() {
        val login = authentication.setup("flo", OLD_PASSWORD, setupSecret)
        val other = insertAdditionalOwner("another")
        val correlation = UUID.randomUUID()
        val target = UUID.randomUUID()
        jdbc.sql("""INSERT INTO action_execution(id,owner_id,idempotency_key,correlation_id,request_hash,status,outcome,created_at,completed_at)
            VALUES(:id,:owner,:key,:correlation,:hash,'completed',CAST(:outcome AS jsonb),CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
            .param("id", UUID.randomUUID()).param("owner", login.user.id).param("key", UUID.randomUUID())
            .param("correlation", correlation).param("hash", "a".repeat(64))
            .param("outcome", """{"status":"succeeded","code":"action.succeeded","correlationId":"$correlation","capability":"power.set","requested":1,"succeeded":1,"failed":0,"targets":[{"targetId":"$target","displayName":"Room lamp","status":"succeeded"}]}""").update()
        activity.record(ActivityCategory.CAPABILITY, "action.proposed", ActivityStatus.PROPOSED, ActivityActorType.USER,
            "web", "action.proposed", login.user.id.toString(), correlation, login.user.id)
        activity.record(ActivityCategory.CAPABILITY, "action.completed", ActivityStatus.SUCCEEDED, ActivityActorType.USER,
            "web", "action.succeeded", login.user.id.toString(), correlation, login.user.id)
        activity.record(ActivityCategory.CAPABILITY, "gateway.command.completed", ActivityStatus.FAILED, ActivityActorType.INTEGRATION,
            "kyrion-gateway", "private-provider-payload", other.toString(), correlation, other)
        mockMvc.perform(get("/v1/activity/timeline/$correlation").header("Authorization", "Bearer ${login.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$.items.length()").value(2))
            .andExpect(jsonPath("$.items[0].eventType").value("action.proposed"))
            .andExpect(jsonPath("$.items[1].eventType").value("action.completed"))
            .andExpect(jsonPath("$.truncated").value(false))
            .andExpect(jsonPath("$.outcome.targets[0].displayName").value("Room lamp"))
        mockMvc.perform(get("/v1/activity/timeline/$correlation")).andExpect(status().isUnauthorized)
    }

    @Test
    fun `setup closes permanently and login persists across service calls`() {
        assertThat(authentication.setupRequired()).isTrue()
        val owner = authentication.setup(" Flo ", OLD_PASSWORD, setupSecret)

        assertThat(authentication.setupRequired()).isFalse()
        assertThat(authentication.authenticate(owner.session.rawToken)?.username).isEqualTo("flo")
        assertThat(authentication.login("FLO", OLD_PASSWORD).user.id).isEqualTo(owner.user.id)
        assertThatThrownBy { authentication.setup("other", OTHER_PASSWORD, setupSecret) }
            .isInstanceOf(SetupAlreadyCompletedException::class.java)
    }

    @Test
    fun `calendar routes authenticate the same bearer session as other workspace routes`() {
        val login = authentication.setup("flo", OLD_PASSWORD, setupSecret)

        mockMvc.perform(get("/v1/calendar/events"))
            .andExpect(status().isUnauthorized)
            .andExpect(jsonPath("$.code").value("UNAUTHENTICATED"))
        mockMvc.perform(get("/v1/calendar/events").header("Authorization", "Bearer ${login.session.rawToken}"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$").isArray)
    }

    @Test
    fun `local calendar creation persists and CRUD remains scoped to its workspace`() {
        val owner = authentication.setup("flo", OLD_PASSWORD, setupSecret)
        val body = """{"title":"Installer review","description":null,"startsAt":"2026-10-12T09:00:00Z","endsAt":"2026-10-12T10:00:00Z","timeZone":"Europe/Zurich","syncToGoogle":false}"""
        mockMvc.perform(post("/v1/calendar/events").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isUnauthorized)
        val result = mockMvc.perform(post("/v1/calendar/events")
            .header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.title").value("Installer review"))
            .andReturn()
        val id = UUID.fromString(com.fasterxml.jackson.module.kotlin.jacksonObjectMapper()
            .readTree(result.response.contentAsString).path("id").asText())
        assertThat(jdbc.sql("SELECT owner_id FROM local_calendar_event WHERE id=:id")
            .param("id", id).query(UUID::class.java).single()).isEqualTo(owner.user.id)
        mockMvc.perform(get("/v1/calendar/events").header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$[0].id").value(id.toString()))

        insertAdditionalOwner("other")
        val other = authentication.login("other", OTHER_PASSWORD)
        mockMvc.perform(get("/v1/calendar/events").header("Authorization", "Bearer ${other.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$").isEmpty)
        mockMvc.perform(put("/v1/calendar/events/$id").header("Authorization", "Bearer ${other.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isNotFound)
        mockMvc.perform(delete("/v1/calendar/events/$id").header("Authorization", "Bearer ${other.session.rawToken}"))
            .andExpect(status().isNotFound)
        mockMvc.perform(put("/v1/calendar/events/$id").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content(body.dropLast(1) + ",\"revision\":0}"))
            .andExpect(status().isConflict).andExpect(jsonPath("$.code").value("CALENDAR_SYNC_CONFLICT"))
        mockMvc.perform(delete("/v1/calendar/events/$id").param("revision","0").header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isConflict)
        mockMvc.perform(put("/v1/calendar/events/$id").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content(body.replace("Installer review", "Updated review")))
            .andExpect(status().isOk).andExpect(jsonPath("$.title").value("Updated review"))
        mockMvc.perform(delete("/v1/calendar/events/$id").header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isOk)
        assertThat(jdbc.sql("SELECT COUNT(*) FROM local_calendar_event WHERE id=:id")
            .param("id", id).query(Int::class.java).single()).isZero()
    }

    @Test
    fun `owner role and primary owner account remain protected over HTTP`() {
        val owner = authentication.setup("flo", OLD_PASSWORD, setupSecret)
        val result = mockMvc.perform(get("/v1/rbac/roles")
            .header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isOk).andReturn()
        val ownerRole = com.fasterxml.jackson.module.kotlin.jacksonObjectMapper()
            .readTree(result.response.contentAsString).first { it.path("key").asText() == "OWNER" }
        mockMvc.perform(put("/v1/rbac/roles/${ownerRole.path("id").asText()}")
            .header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""{"key":"OWNER","name":"Owner","permissions":[]}"""))
            .andExpect(status().isConflict)
            .andExpect(jsonPath("$.code").value("SYSTEM_ROLE_PROTECTED"))
        mockMvc.perform(put("/v1/rbac/users/${owner.user.id}/enabled").param("value", "false")
            .header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isConflict)
            .andExpect(jsonPath("$.code").value("LAST_OWNER_PROTECTED"))
        assertThat(authentication.authenticate(owner.session.rawToken)?.id).isEqualTo(owner.user.id)
    }

    @Test
    fun `deactivating an invited member revokes access and records the actual actor`() {
        val owner = authentication.setup("flo", OLD_PASSWORD, setupSecret)
        val invitation = authentication.createInvitation(owner.session.rawToken)
        val friend = authentication.register("friend", OTHER_PASSWORD, invitation.code)
        mockMvc.perform(put("/v1/rbac/users/${friend.user.id}/enabled").param("value", "false")
            .header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isNoContent)
        assertThat(authentication.authenticate(friend.session.rawToken)).isNull()
        mockMvc.perform(get("/v1/devices").header("Authorization", "Bearer ${friend.session.rawToken}"))
            .andExpect(status().isUnauthorized)
        val event = activity.recent(owner.user.id, 100).single { it.eventType == "rbac.user.deactivated" }
        assertThat(event.actorId).isEqualTo(owner.user.id.toString())
        assertThat(event.ownerId).isEqualTo(owner.user.id)
        mockMvc.perform(put("/v1/rbac/users/${friend.user.id}/enabled").param("value", "true")
            .header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isNoContent)
        assertThat(authentication.authenticate(friend.session.rawToken)).isNull()
        assertThat(authentication.login("friend", OTHER_PASSWORD).user.id).isEqualTo(friend.user.id)
    }

    @Test
    fun `password change revokes every existing session and persists only the new password`() {
        val owner = authentication.setup("flo", OLD_PASSWORD, setupSecret)
        val secondSession = authentication.login("flo", OLD_PASSWORD)

        val rotated = authentication.changePassword(owner.session.rawToken, OLD_PASSWORD, NEW_PASSWORD)

        assertThat(authentication.authenticate(owner.session.rawToken)).isNull()
        assertThat(authentication.authenticate(secondSession.session.rawToken)).isNull()
        assertThat(authentication.authenticate(rotated.session.rawToken)?.id).isEqualTo(owner.user.id)
        assertThatThrownBy { authentication.login("flo", OLD_PASSWORD) }
            .isInstanceOf(InvalidCredentialsException::class.java)
        assertThat(authentication.login("flo", NEW_PASSWORD).user.id).isEqualTo(owner.user.id)
        val storedHash = jdbc.sql("SELECT password_hash FROM user_account WHERE id = :id")
            .param("id", owner.user.id).query(String::class.java).single()
        assertThat(storedHash).doesNotContain(NEW_PASSWORD)
        assertThat(passwordHashing.matches(NEW_PASSWORD, storedHash)).isTrue()
    }

    @Test
    fun `conversation queries enforce owner isolation in PostgreSQL`() {
        val first = authentication.setup("first", OLD_PASSWORD, setupSecret).user
        val second = insertAdditionalOwner("second")
        val now = Instant.parse("2026-08-03T20:00:00Z")
        val conversation = Conversation(
            UUID.randomUUID(), "Private conversation", now, now,
            listOf(ConversationMessage(UUID.randomUUID(), "user", "private text", now)),
        )

        conversations.replace(first.id, conversation)

        assertThat(conversations.find(first.id, conversation.id)).isEqualTo(conversation)
        assertThat(conversations.find(second, conversation.id)).isNull()
        assertThat(conversations.recent(second, 30)).isEmpty()
        assertThatThrownBy { conversations.replace(second, conversation.copy(title = "stolen")) }
            .isInstanceOf(ConversationNotFoundException::class.java)
        assertThatThrownBy {
            conversations.appendMessage(
                second, conversation.id, "stolen",
                ConversationMessage(UUID.randomUUID(), "user", "intrusion", now), true, now,
            )
        }.isInstanceOf(ConversationNotFoundException::class.java)
        assertThat(conversations.rename(second, conversation.id, "stolen", now)).isNull()
        assertThat(conversations.delete(second, conversation.id)).isFalse()
        assertThat(conversations.rename(first.id, conversation.id, "Renamed", now.plusSeconds(1))?.title).isEqualTo("Renamed")
        assertThat(conversations.delete(first.id, conversation.id)).isTrue()
        assertThat(conversations.find(first.id, conversation.id)).isNull()
    }

    @Test
    fun `HTTP authentication lifecycle exposes stable status codes and protects private routes`() {
        mockMvc.perform(get("/v1/activity"))
            .andExpect(status().isUnauthorized)
            .andExpect(jsonPath("$.code").value("UNAUTHENTICATED"))

        val setupResult = mockMvc.perform(
            post("/v1/auth/setup").header("X-Kyrion-Setup-Secret", setupSecret).contentType(MediaType.APPLICATION_JSON)
                .content("""{"username":"flo","password":"$OLD_PASSWORD"}"""),
        ).andExpect(status().isCreated)
            .andExpect(jsonPath("$.user.username").value("flo"))
            .andExpect(jsonPath("$.sessionToken").isString)
            .andReturn()
        val token = Regex("\"sessionToken\":\"([^\"]+)\"").find(setupResult.response.contentAsString)!!.groupValues[1]

        mockMvc.perform(
            post("/v1/auth/setup").header("X-Kyrion-Setup-Secret", setupSecret).contentType(MediaType.APPLICATION_JSON)
                .content("""{"username":"other","password":"$OTHER_PASSWORD"}"""),
        ).andExpect(status().isConflict)
            .andExpect(jsonPath("$.code").value("SETUP_ALREADY_COMPLETED"))

        mockMvc.perform(get("/v1/auth/me").header("Authorization", "Bearer $token"))
            .andExpect(status().isOk).andExpect(jsonPath("$.username").value("flo"))

        mockMvc.perform(
            post("/v1/auth/login").contentType(MediaType.APPLICATION_JSON)
                .content("""{"username":"flo","password":"wrong-password-value"}"""),
        ).andExpect(status().isUnauthorized)
            .andExpect(jsonPath("$.code").value("UNAUTHENTICATED"))

        mockMvc.perform(post("/v1/auth/logout").header("Authorization", "Bearer $token"))
            .andExpect(status().isNoContent)
        mockMvc.perform(get("/v1/auth/me").header("Authorization", "Bearer $token"))
            .andExpect(status().isUnauthorized)
    }

    @Test
    fun `HTTP session management lists active sessions and enforces owner scoped revocation`() {
        val currentToken = setupToken()
        val otherSession = authentication.login("flo", OLD_PASSWORD).session

        mockMvc.perform(get("/v1/auth/sessions").header("Authorization", "Bearer $currentToken"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.length()").value(2))
            .andExpect(jsonPath("$[*].current").value(org.hamcrest.Matchers.containsInAnyOrder(true, false)))
            .andExpect(jsonPath("$[*].tokenHash").doesNotExist())

        val secondOwnerId = insertAdditionalOwner("second")
        val secondOwnerSession = authentication.login("second", OTHER_PASSWORD).session
        mockMvc.perform(
            delete("/v1/auth/sessions/${secondOwnerSession.session.id}")
                .header("Authorization", "Bearer $currentToken"),
        ).andExpect(status().isNotFound)
            .andExpect(jsonPath("$.code").value("AUTH_SESSION_NOT_FOUND"))
        assertThat(authentication.authenticate(secondOwnerSession.rawToken)?.id).isEqualTo(secondOwnerId)

        mockMvc.perform(
            delete("/v1/auth/sessions/${otherSession.session.id}")
                .header("Authorization", "Bearer $currentToken"),
        ).andExpect(status().isNoContent)
        assertThat(authentication.authenticate(otherSession.rawToken)).isNull()
    }

    @Test
    fun `HTTP activity feed includes owner and safe system events but excludes another owner`() {
        val firstToken = setupToken()
        val firstOwner = authentication.authenticate(firstToken)!!.id
        val secondOwner = insertAdditionalOwner("second")
        val firstCorrelation = UUID.randomUUID()
        val secondCorrelation = UUID.randomUUID()
        activity.record(
            ActivityCategory.INTEGRATION, "integration.first", ActivityStatus.SUCCEEDED,
            ActivityActorType.INTEGRATION, "test-adapter", "integration.first", correlationId = firstCorrelation,
            ownerId = firstOwner,
        )
        activity.record(
            ActivityCategory.INTEGRATION, "integration.second", ActivityStatus.SUCCEEDED,
            ActivityActorType.INTEGRATION, "test-adapter", "integration.second", correlationId = secondCorrelation,
            ownerId = secondOwner,
        )

        val response = mockMvc.perform(get("/v1/activity").header("Authorization", "Bearer $firstToken"))
            .andExpect(status().isOk)
            .andReturn().response.contentAsString

        assertThat(response).contains(firstCorrelation.toString())
        assertThat(response).doesNotContain(secondCorrelation.toString())
        assertThat(response).doesNotContain("ownerId")
        assertThat(
            jdbc.sql("SELECT owner_id FROM activity_event WHERE correlation_id = :id")
                .param("id", firstCorrelation).query(UUID::class.java).single(),
        ).isEqualTo(firstOwner)
    }

    @Test
    fun `HTTP retention policy is owner scoped typed and non enforcing`() {
        val firstToken = setupToken()
        mockMvc.perform(get("/v1/retention").header("Authorization", "Bearer $firstToken"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.conversations").value("keep_forever"))
            .andExpect(jsonPath("$.enforcementActive").value(false))

        mockMvc.perform(
            put("/v1/retention").header("Authorization", "Bearer $firstToken")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"conversations":"365_days","activity":"3_years","personalMemory":"90_days"}"""),
        ).andExpect(status().isOk)
            .andExpect(jsonPath("$.conversations").value("365_days"))
            .andExpect(jsonPath("$.enforcementActive").value(false))

        insertAdditionalOwner("second")
        val secondToken = authentication.login("second", OTHER_PASSWORD).session.rawToken
        mockMvc.perform(get("/v1/retention").header("Authorization", "Bearer $secondToken"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.conversations").value("keep_forever"))

        mockMvc.perform(
            put("/v1/retention").header("Authorization", "Bearer $firstToken")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"conversations":"7_days","activity":"3_years","personalMemory":"90_days"}"""),
        ).andExpect(status().isBadRequest)
    }

    @Test
    fun `retention cleanup previews and deletes only expired owner records after confirmation`() {
        val token = setupToken()
        val ownerId = authentication.authenticate(token)!!.id
        val old = Instant.parse("2020-01-01T00:00:00Z")
        val recent = Instant.now()
        conversations.replace(ownerId, Conversation(UUID.randomUUID(), "Expired", old, old, listOf()))
        conversations.replace(ownerId, Conversation(UUID.randomUUID(), "Current", recent, recent, listOf()))
        val secondOwner = insertAdditionalOwner("retention-second")
        conversations.replace(secondOwner, Conversation(UUID.randomUUID(), "Other owner expired", old, old, listOf()))
        jdbc.sql("""INSERT INTO personal_memory(id,owner_id,category,content,sensitivity,origin,status,created_at,updated_at,confirmed_at)
            VALUES(:id,:owner,'other','expired memory','standard','explicit','confirmed',:old,:old,:old)""")
            .param("id", UUID.randomUUID()).param("owner", ownerId).param("old", Timestamp.from(old)).update()
        activity.record(ActivityCategory.SECURITY, "recent.event", ActivityStatus.SUCCEEDED, ActivityActorType.USER,
            "test", "recent.event", actorId = ownerId.toString(), ownerId = ownerId)
        jdbc.sql("UPDATE activity_event SET occurred_at=:old WHERE owner_id=:owner")
            .param("old", Timestamp.from(old)).param("owner", ownerId).update()

        mockMvc.perform(put("/v1/retention").header("Authorization", "Bearer $token")
            .contentType(MediaType.APPLICATION_JSON)
            .content("""{"conversations":"30_days","activity":"30_days","personalMemory":"30_days"}"""))
            .andExpect(status().isOk)
        mockMvc.perform(get("/v1/retention/preview").header("Authorization", "Bearer $token"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.conversations.records").value(1))
            .andExpect(jsonPath("$.activity.records").value(2))
            .andExpect(jsonPath("$.personalMemory.records").value(1))
        mockMvc.perform(post("/v1/retention/cleanup").header("Authorization", "Bearer $token")
            .contentType(MediaType.APPLICATION_JSON).content("""{"confirmation":"NO"}"""))
            .andExpect(status().isConflict)
            .andExpect(jsonPath("$.code").value("RETENTION_CLEANUP_CONFIRMATION_REQUIRED"))
        mockMvc.perform(post("/v1/retention/cleanup").header("Authorization", "Bearer $token")
            .contentType(MediaType.APPLICATION_JSON).content("""{"confirmation":"DELETE"}"""))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.conversationsDeleted").value(1))
            .andExpect(jsonPath("$.activityDeleted").value(2))
            .andExpect(jsonPath("$.personalMemoriesDeleted").value(1))
        assertThat(conversations.recent(ownerId, 10).map { it.title }).containsExactly("Current")
        assertThat(conversations.recent(secondOwner, 10).map { it.title }).containsExactly("Other owner expired")
        assertThat(jdbc.sql("SELECT COUNT(*) FROM activity_event WHERE owner_id=:owner AND event_type='retention.cleanup.executed'")
            .param("owner", ownerId).query(Int::class.java).single()).isEqualTo(1)
        mockMvc.perform(get("/v1/activity/integrity").header("Authorization", "Bearer $token"))
            .andExpect(status().isOk).andExpect(jsonPath("$.owner.valid").value(true))
    }

    @Test
    fun `activity integrity verification detects database tampering`() {
        val token = setupToken()
        val ownerId = authentication.authenticate(token)!!.id
        activity.record(ActivityCategory.SECURITY, "integrity.test", ActivityStatus.SUCCEEDED, ActivityActorType.USER,
            "test", "integrity.test", actorId = ownerId.toString(), ownerId = ownerId)
        mockMvc.perform(get("/v1/activity/integrity").header("Authorization", "Bearer $token"))
            .andExpect(status().isOk)
            .andExpect(jsonPath("$.owner.valid").value(true))
            .andExpect(jsonPath("$.owner.sealedEvents").value(org.hamcrest.Matchers.greaterThan(0)))
        jdbc.sql("UPDATE activity_event SET summary_code='tampered' WHERE owner_id=:owner AND event_type='integrity.test'")
            .param("owner", ownerId).update()
        mockMvc.perform(get("/v1/activity/integrity").header("Authorization", "Bearer $token"))
            .andExpect(status().isOk).andExpect(jsonPath("$.owner.valid").value(false))
    }

    @Test
    fun `HTTP personal backup exports encrypted owner data without credentials`() {
        val token = setupToken()
        val ownerId = authentication.authenticate(token)!!.id
        val now = Instant.parse("2026-08-22T15:00:00Z")
        conversations.replace(ownerId, Conversation(UUID.randomUUID(), "Backup conversation", now, now,
            listOf(ConversationMessage(UUID.randomUUID(), "user", "private backup content", now))))

        val result = mockMvc.perform(
            post("/v1/backups/personal").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"passphrase":"a-strong-portable-passphrase"}"""),
        ).andExpect(status().isOk)
            .andExpect(jsonPath("$.format").value("kyrion-personal-backup"))
            .andExpect(jsonPath("$.formatVersion").value(1))
            .andExpect(jsonPath("$.algorithm").value("AES-256-GCM"))
            .andReturn().response.contentAsString

        assertThat(result).doesNotContain("private backup content")
        assertThat(result).doesNotContain("sessionToken")
        mockMvc.perform(
            post("/v1/backups/personal").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON).content("""{"passphrase":"too-short"}"""),
        ).andExpect(status().isBadRequest)
    }

    @Test
    fun `personal backup imports into another owner once without overwriting source data`() {
        val firstToken=setupToken();val firstOwner=authentication.authenticate(firstToken)!!.id;val now=Instant.parse("2026-08-22T15:00:00Z")
        conversations.replace(firstOwner,Conversation(UUID.randomUUID(),"Portable conversation",now,now,listOf(ConversationMessage(UUID.randomUUID(),"user","portable private text",now))))
        val envelope=mockMvc.perform(post("/v1/backups/personal").header("Authorization","Bearer $firstToken").contentType(MediaType.APPLICATION_JSON).content("""{"passphrase":"a-strong-portable-passphrase"}"""))
            .andExpect(status().isOk).andReturn().response.contentAsString
        val secondOwner=insertAdditionalOwner("second");val secondToken=authentication.login("second",OTHER_PASSWORD).session.rawToken
        val importBody="""{"envelope":$envelope,"passphrase":"a-strong-portable-passphrase","confirmation":"IMPORT"}"""
        mockMvc.perform(post("/v1/backups/personal/import").header("Authorization","Bearer $secondToken").contentType(MediaType.APPLICATION_JSON).content(importBody))
            .andExpect(status().isOk).andExpect(jsonPath("$.conversationsImported").value(1)).andExpect(jsonPath("$.messagesImported").value(1))
        mockMvc.perform(post("/v1/backups/personal/import").header("Authorization","Bearer $secondToken").contentType(MediaType.APPLICATION_JSON).content(importBody))
            .andExpect(status().isOk).andExpect(jsonPath("$.conversationsImported").value(0)).andExpect(jsonPath("$.conversationsSkipped").value(1))
        assertThat(conversations.recent(secondOwner,10).map{it.title}).containsExactly("Portable conversation")
        assertThat(conversations.recent(firstOwner,10).map{it.title}).containsExactly("Portable conversation")
        assertThat(jdbc.sql("SELECT COUNT(*) FROM conversation WHERE title='Portable conversation'").query(Int::class.java).single()).isEqualTo(2)
    }

    @Test
    fun `HTTP conversation lifecycle supports save rename and confirmed deletion semantics`() {
        val token = setupToken()
        val conversationId = UUID.randomUUID()
        val messageId = UUID.randomUUID()
        val createdAt = "2026-08-03T20:00:00Z"

        mockMvc.perform(
            put("/v1/conversations/$conversationId").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"title":"Initial title","messages":[{"id":"$messageId","role":"user","content":"Hello","createdAt":"$createdAt"}]}"""),
        ).andExpect(status().isOk).andExpect(jsonPath("$.title").value("Initial title"))

        mockMvc.perform(
            patch("/v1/conversations/$conversationId").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON).content("""{"title":"Renamed title"}"""),
        ).andExpect(status().isOk).andExpect(jsonPath("$.title").value("Renamed title"))

        mockMvc.perform(delete("/v1/conversations/$conversationId").header("Authorization", "Bearer $token"))
            .andExpect(status().isNoContent)
        mockMvc.perform(get("/v1/conversations/$conversationId").header("Authorization", "Bearer $token"))
            .andExpect(status().isNotFound).andExpect(jsonPath("$.code").value("CONVERSATION_NOT_FOUND"))
    }

    @Test
    fun `HTTP cloud consent cannot bypass server policy and creates no conversation`() {
        val token = setupToken()
        val id = UUID.randomUUID()
        mockMvc.perform(
            post("/v1/conversations/$id/turns").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"title":"Cloud denial","externalProvider":"openai","externalConsent":"current_message","message":{"id":"${UUID.randomUUID()}","role":"user","content":"Synthetic test","createdAt":"2026-10-30T12:00:00Z"}}""")
        )
            .andExpect(status().isForbidden).andExpect(jsonPath("$.code").value("CLOUD_NOT_ALLOWED"))
        assertThat(
            jdbc.sql("SELECT COUNT(*) FROM conversation WHERE id=:id").param("id", id).query(Int::class.java).single()
        ).isZero()
    }

    @Test
    fun `Core appends authoritative turns in order and persists deterministic compaction metadata`() {
        val token = setupToken()
        val conversationId = UUID.randomUUID()
        val firstUser = UUID.randomUUID()
        val firstAssistant = UUID.randomUUID()
        val secondUser = UUID.randomUUID()
        val createdAt = "2026-08-03T20:00:00Z"
        val longContent = "A".repeat(700)

        mockMvc.perform(
            post("/v1/conversations/$conversationId/turns").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"title":"Authoritative","tokenBudget":256,"message":{"id":"$firstUser","role":"user","content":"$longContent","createdAt":"$createdAt"}}"""),
        ).andExpect(status().isOk)
            .andExpect(jsonPath("$.messages[0].role").value("user"))
            .andExpect(jsonPath("$.compacted").value(false))

        mockMvc.perform(
            post("/v1/conversations/$conversationId/turns/complete").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"turnId":"$firstUser","status":"completed","message":{"id":"$firstAssistant","role":"assistant","content":"$longContent","createdAt":"$createdAt"}}"""),
        ).andExpect(status().isOk)

        mockMvc.perform(
            post("/v1/conversations/$conversationId/turns").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"title":"Browser cannot replace this","tokenBudget":256,"message":{"id":"$secondUser","role":"user","content":"Newest question","createdAt":"$createdAt"}}"""),
        ).andExpect(status().isOk)
            .andExpect(jsonPath("$.compacted").value(true))
            .andExpect(jsonPath("$.messages[0].content").value(org.hamcrest.Matchers.startsWith("Older conversation context")))
            .andExpect(jsonPath("$.messages[2].content").value("Newest question"))

        val storedMessages = conversations.find(authentication.login("flo", OLD_PASSWORD).user.id, conversationId)!!.messages
        assertThat(storedMessages.map { it.id }).containsExactly(firstUser, firstAssistant, secondUser)
        assertThat(
            jdbc.sql("SELECT COUNT(*) FROM conversation_context_summary WHERE conversation_id = :id")
                .param("id", conversationId).query(Int::class.java).single(),
        ).isEqualTo(1)
        assertThat(
            jdbc.sql("SELECT status FROM conversation_turn WHERE id = :id")
                .param("id", firstUser).query(String::class.java).single(),
        ).isEqualTo("completed")
    }

    @Test
    fun `turn lifecycle records stopped visible output and failed empty output`() {
        val token = setupToken()
        val conversationId = UUID.randomUUID()
        val stoppedTurn = UUID.randomUUID()
        val stoppedAssistant = UUID.randomUUID()
        val failedTurn = UUID.randomUUID()
        val createdAt = "2026-08-04T10:00:00Z"

        startHttpTurn(token, conversationId, stoppedTurn, "Stop this", createdAt)
        mockMvc.perform(
            post("/v1/conversations/$conversationId/turns/complete").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"turnId":"$stoppedTurn","status":"stopped","message":{"id":"$stoppedAssistant","role":"assistant","content":"Visible partial answer","createdAt":"$createdAt"}}"""),
        ).andExpect(status().isOk)

        startHttpTurn(token, conversationId, failedTurn, "Fail this", createdAt)
        mockMvc.perform(
            post("/v1/conversations/$conversationId/turns/complete").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"turnId":"$failedTurn","status":"failed","errorCode":"MODEL_UNAVAILABLE"}"""),
        ).andExpect(status().isOk)

        assertThat(turnStatus(stoppedTurn)).isEqualTo("stopped")
        assertThat(turnStatus(failedTurn)).isEqualTo("failed")
        assertThat(
            jdbc.sql("SELECT error_code FROM conversation_turn WHERE id = :id").param("id", failedTurn)
                .query(String::class.java).single(),
        ).isEqualTo("MODEL_UNAVAILABLE")
    }

    @Test
    fun `personal memory requires opt in proposal confirmation and owner scoped mutation`() {
        val token = setupToken()
        val ownerId = authentication.login("flo", OLD_PASSWORD).user.id
        val conversationId = UUID.randomUUID()
        val sourceMessageId = UUID.randomUUID()
        val createdAt = "2026-08-04T10:00:00Z"
        startHttpTurn(token, conversationId, sourceMessageId, "Remember this", createdAt)

        val proposalBody = """{"category":"project","content":"Kyrion is my long-running project","sensitivity":"standard","sourceConversationId":"$conversationId","sourceMessageId":"$sourceMessageId"}"""
        mockMvc.perform(
            post("/v1/memory/proposals").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON).content(proposalBody),
        ).andExpect(status().isConflict).andExpect(jsonPath("$.code").value("MEMORY_DISABLED"))

        mockMvc.perform(
            put("/v1/memory/settings").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON).content("""{"enabled":true}"""),
        ).andExpect(status().isOk).andExpect(jsonPath("$.enabled").value(true))

        val proposalResult = mockMvc.perform(
            post("/v1/memory/proposals").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON).content(proposalBody),
        ).andExpect(status().isCreated).andExpect(jsonPath("$.status").value("proposed")).andReturn()
        val memoryId = UUID.fromString(Regex("\"id\":\"([^\"]+)\"").find(proposalResult.response.contentAsString)!!.groupValues[1])

        mockMvc.perform(post("/v1/memory/$memoryId/confirm").header("Authorization", "Bearer $token"))
            .andExpect(status().isOk).andExpect(jsonPath("$.status").value("confirmed"))
        mockMvc.perform(
            patch("/v1/memory/$memoryId").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"category":"project","content":"Kyrion is my local-first project","sensitivity":"standard"}"""),
        ).andExpect(status().isOk).andExpect(jsonPath("$.content").value("Kyrion is my local-first project"))

        val secondOwner = insertAdditionalOwner("second")
        assertThat(memories.find(secondOwner, memoryId)).isNull()
        assertThat(memories.find(ownerId, memoryId)?.status?.name).isEqualTo("confirmed")

        val relevantTurn = UUID.randomUUID()
        mockMvc.perform(
            post("/v1/conversations/$conversationId/turns").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"title":"Lifecycle","tokenBudget":3072,"message":{"id":"$relevantTurn","role":"user","content":"How is the Kyrion project going?","createdAt":"$createdAt"}}"""),
        ).andExpect(status().isOk)
            .andExpect(jsonPath("$.usedMemories[0].id").value(memoryId.toString()))
            .andExpect(jsonPath("$.usedMemories[0].content").value("Kyrion is my local-first project"))

        val conflictResult = mockMvc.perform(
            post("/v1/memory/proposals").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"category":"project","content":"Kyrion is my new local-first project","sensitivity":"standard"}"""),
        ).andExpect(status().isCreated)
            .andExpect(jsonPath("$.conflictsWithMemoryId").value(memoryId.toString())).andReturn()
        val replacementId = UUID.fromString(Regex("\"id\":\"([^\"]+)\"").find(conflictResult.response.contentAsString)!!.groupValues[1])
        mockMvc.perform(
            post("/v1/memory/$replacementId/confirm?resolution=replace").header("Authorization", "Bearer $token"),
        ).andExpect(status().isOk).andExpect(jsonPath("$.status").value("confirmed"))
        assertThat(memories.find(ownerId, memoryId)?.status?.name).isEqualTo("superseded")

        mockMvc.perform(delete("/v1/memory/$memoryId").header("Authorization", "Bearer $token"))
            .andExpect(status().isNoContent)
        mockMvc.perform(delete("/v1/memory/$replacementId").header("Authorization", "Bearer $token"))
            .andExpect(status().isNoContent)
        assertThat(memories.find(ownerId, memoryId)).isNull()
    }

    @Test
    fun `registration preserves revoked permissions during parallel invitations and reseeding`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val role = rbac.roles(owner.user.id).single { it.key == "USER" }
        rbac.updateRole(owner.user.id, role.id, RoleRequest("USER", "User", role.permissions - "devices:execute"))
        val invitations = (1..3).map { authentication.createInvitation(owner.session.rawToken) }
        val executor = java.util.concurrent.Executors.newFixedThreadPool(3)
        try {
            val members = executor.invokeAll(invitations.mapIndexed { index, invitation -> java.util.concurrent.Callable {
                authentication.register("member$index", OTHER_PASSWORD, invitation.code)
            } }).map { it.get() }
            members.forEach {
                rbac.initializeUser(it.user.id, owner.user.id, false)
                assertThat(rbac.permissions(it.user.id)).doesNotContain("devices:execute")
            }
            assertThat(rbac.roles(owner.user.id).single { it.id == role.id }.permissions).isEqualTo(role.permissions - "devices:execute")
        } finally { executor.shutdownNow() }
    }

    @Test
    fun `delegated admin manages only bounded roles in the owner workspace with correct audit actor`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val admin = authentication.register("admin", OTHER_PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        val user = authentication.register("member", OTHER_PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        val roles = rbac.roles(owner.user.id)
        rbac.assignRoles(owner.user.id, admin.user.id, setOf(roles.single { it.key == "ADMIN" }.id))
        val created = mockMvc.perform(post("/v1/rbac/roles").header("Authorization", "Bearer ${admin.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content("""{"key":"lamps","name":"Lamps","permissions":["devices:read"]}"""))
            .andExpect(status().isCreated).andReturn()
        val roleId = UUID.fromString(com.fasterxml.jackson.module.kotlin.jacksonObjectMapper().readTree(created.response.contentAsString).path("id").asText())
        assertThat(rbac.roles(owner.user.id).map { it.id }).contains(roleId)
        val event = activity.recent(owner.user.id, 100).single { it.eventType == "rbac.role.created" }
        assertThat(event.actorId).isEqualTo(admin.user.id.toString())
        assertThat(event.summaryCode).isEqualTo(roleId.toString())
        assertThatThrownBy { rbac.assignRoles(admin.user.id, user.user.id, setOf(roles.single { it.key == "OWNER" }.id)) }.isInstanceOf(ForbiddenException::class.java)
        assertThatThrownBy { rbac.assignRoles(admin.user.id, admin.user.id, setOf(roleId)) }.isInstanceOf(ForbiddenException::class.java)
        assertThatThrownBy { rbac.createRole(admin.user.id, RoleRequest("private", "Private", setOf("personal_memories:read"))) }.isInstanceOf(ForbiddenException::class.java)
        assertThatThrownBy { rbac.updateRole(admin.user.id, roles.single { it.key == "ADMIN" }.id, RoleRequest("ADMIN", "Admin", emptySet())) }.isInstanceOf(ForbiddenException::class.java)
        rbac.assignRoles(owner.user.id, user.user.id, setOf(roleId))
        rbac.assignRoles(admin.user.id, user.user.id, setOf(roleId))
        rbac.deactivate(admin.user.id, user.user.id, false)
        rbac.deactivate(admin.user.id, user.user.id, true)
        mockMvc.perform(post("/v1/auth/invitations").header("Authorization", "Bearer ${admin.session.rawToken}"))
            .andExpect(status().isCreated)
        mockMvc.perform(post("/v1/rbac/roles").header("Authorization", "Bearer ${user.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content("""{"key":"bad","name":"Bad","permissions":[]}"""))
            .andExpect(status().isUnauthorized)
    }

    @Test
    fun `cross workspace deactivation cannot revoke foreign sessions`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val foreign = insertAdditionalOwner("foreign")
        val login = authentication.login("foreign", OTHER_PASSWORD)
        assertThatThrownBy { rbac.deactivate(owner.user.id, foreign, false) }.isInstanceOf(RoleNotFoundException::class.java)
        assertThat(authentication.authenticate(login.session.rawToken)).isNotNull()
    }

    @Test
    fun `bootstrap rejects missing and invalid secrets and only one parallel owner wins`() {
        val body = """{"username":"owner","password":"$OLD_PASSWORD"}"""
        mockMvc.perform(post("/v1/auth/setup").contentType(MediaType.APPLICATION_JSON).content(body))
            .andExpect(status().isForbidden).andExpect(jsonPath("$.code").value("BOOTSTRAP_FORBIDDEN"))
        assertThatThrownBy { authentication.setup("owner", OLD_PASSWORD, "invalid") }.isInstanceOf(BootstrapForbiddenException::class.java)
        val executor = java.util.concurrent.Executors.newFixedThreadPool(2)
        try {
            val results = executor.invokeAll((1..2).map { index -> java.util.concurrent.Callable {
                runCatching { authentication.setup("owner$index", OLD_PASSWORD, setupSecret) }
            } }).map { it.get() }
            assertThat(results.count { it.isSuccess }).isEqualTo(1)
            assertThat(results.single { it.isFailure }.exceptionOrNull()).isInstanceOf(SetupAlreadyCompletedException::class.java)
        } finally { executor.shutdownNow() }
        assertThatThrownBy { authentication.setup("again", OLD_PASSWORD, setupSecret) }.isInstanceOf(SetupAlreadyCompletedException::class.java)
        assertThat(jdbc.sql("SELECT initialized FROM installation_bootstrap_state").query(Boolean::class.java).single()).isTrue()
    }

    @Test
    fun `transaction rollback restores permissions and registration invitation`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val role = rbac.roles(owner.user.id).single { it.key == "USER" }
        assertThatThrownBy { transactions.executeWithoutResult {
            rbac.updateRole(owner.user.id, role.id, RoleRequest("USER", "User", emptySet()))
            throw IllegalStateException("simulated failure")
        } }.isInstanceOf(IllegalStateException::class.java)
        assertThat(rbac.roles(owner.user.id).single { it.id == role.id }.permissions).isEqualTo(role.permissions)
        val invitation = authentication.createInvitation(owner.session.rawToken)
        assertThatThrownBy { transactions.executeWithoutResult {
            authentication.register("rollback", OTHER_PASSWORD, invitation.code)
            throw IllegalStateException("simulated failure")
        } }.isInstanceOf(IllegalStateException::class.java)
        assertThat(authentication.register("retry", OTHER_PASSWORD, invitation.code).user.username).isEqualTo("retry")
        assertThat(jdbc.sql("SELECT COUNT(*) FROM user_account WHERE username='rollback'").query(Int::class.java).single()).isZero()
    }

    @Test
    fun `calendar permissions defaults and audit protect shared resources and private content`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val member = authentication.register("member", OTHER_PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        val body = """{"title":"Private title","description":"Never audit this","startsAt":"2026-10-12T09:00:00Z","endsAt":"2026-10-12T10:00:00Z"}"""
        val header = "Bearer ${member.session.rawToken}"
        mockMvc.perform(get("/v1/calendar/events").header("Authorization", header)).andExpect(status().isForbidden)
        mockMvc.perform(post("/v1/calendar/events").header("Authorization", header).contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isForbidden)
        val role = rbac.createRole(owner.user.id, RoleRequest("calendar_reader", "Calendar reader", setOf("calendar:read")))
        rbac.assignRoles(owner.user.id, member.user.id, setOf(role.id))
        mockMvc.perform(get("/v1/calendar/events").header("Authorization", header)).andExpect(status().isOk)
        mockMvc.perform(post("/v1/calendar/events").header("Authorization", header).contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isForbidden)
        for (value in listOf<String?>(null, "true", "false")) {
            val payload = if (value == null) body else body.dropLast(1) + ",\"syncToGoogle\":$value}"
            mockMvc.perform(post("/v1/calendar/events").header("Authorization", "Bearer ${owner.session.rawToken}").contentType(MediaType.APPLICATION_JSON).content(payload))
                .andExpect(status().isOk).andExpect(jsonPath("$.syncToGoogle").value(value == "true"))
        }
        mockMvc.perform(post("/v1/calendar/events").header("Authorization", "Bearer ${owner.session.rawToken}").contentType(MediaType.APPLICATION_JSON)
            .content(body.dropLast(1) + ",\"syncToGoogle\":{}}"))
            .andExpect(status().isBadRequest)
        for (invalid in listOf("\"true\"", "1", "[]")) {
            mockMvc.perform(post("/v1/calendar/events").header("Authorization", "Bearer ${owner.session.rawToken}")
                .contentType(MediaType.APPLICATION_JSON).content(body.dropLast(1) + ",\"syncToGoogle\":$invalid}"))
                .andExpect(status().isBadRequest)
        }
        assertThat(activity.recent(owner.user.id, 100).filter { it.eventType.startsWith("calendar.") }).hasSize(3)
            .allMatch { it.actorId == owner.user.id.toString() && !it.summaryCode.contains("Private") && !it.summaryCode.contains("Never") }
        mockMvc.perform(post("/v1/calendar/events").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content(body.dropLast(1) + ",\"timeZone\":\"Not/AZone\"}"))
            .andExpect(status().isBadRequest).andExpect(jsonPath("$.code").value("CALENDAR_EVENT_INVALID"))
        val id = jdbc.sql("SELECT id FROM local_calendar_event LIMIT 1").query(UUID::class.java).single()
        mockMvc.perform(put("/v1/calendar/events/$id").header("Authorization", header).contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isForbidden)
        mockMvc.perform(delete("/v1/calendar/events/$id").header("Authorization", header)).andExpect(status().isForbidden)
    }

    @Test
    fun `audit write failure rolls back setup roles account changes and calendar writes`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val member = authentication.register("member", OTHER_PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        val role = rbac.roles(owner.user.id).single { it.key == "USER" }
        val invitation = authentication.createInvitation(owner.session.rawToken)
        jdbc.sql("""CREATE FUNCTION reject_security_test_audit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'injected audit failure'; END; $$""").update()
        jdbc.sql("CREATE TRIGGER reject_security_test_audit BEFORE INSERT ON activity_event FOR EACH ROW EXECUTE FUNCTION reject_security_test_audit()").update()
        try {
            assertThatThrownBy { rbac.updateRole(owner.user.id, role.id, RoleRequest("USER", "User", emptySet())) }.isInstanceOf(org.springframework.dao.DataAccessException::class.java)
            assertThat(rbac.roles(owner.user.id).single { it.id == role.id }.permissions).isEqualTo(role.permissions)
            assertThatThrownBy { rbac.assignRoles(owner.user.id, member.user.id, setOf(rbac.roles(owner.user.id).single { it.key == "VIEWER" }.id)) }
                .isInstanceOf(org.springframework.dao.DataAccessException::class.java)
            assertThat(rbac.permissions(member.user.id)).isEqualTo(role.permissions)
            assertThatThrownBy { authentication.register("audit_rollback", OTHER_PASSWORD, invitation.code) }
                .isInstanceOf(org.springframework.dao.DataAccessException::class.java)
            assertThatThrownBy { rbac.deactivate(owner.user.id, member.user.id, false) }.isInstanceOf(org.springframework.dao.DataAccessException::class.java)
            assertThat(authentication.authenticate(member.session.rawToken)).isNotNull()
            val count = jdbc.sql("SELECT COUNT(*) FROM local_calendar_event").query(Int::class.java).single()
            assertThatThrownBy { mockMvc.perform(post("/v1/calendar/events").header("Authorization", "Bearer ${owner.session.rawToken}")
                .contentType(MediaType.APPLICATION_JSON).content("""{"title":"Rollback","startsAt":"2026-10-12T09:00:00Z","endsAt":"2026-10-12T10:00:00Z"}""")) }.isInstanceOf(jakarta.servlet.ServletException::class.java)
            assertThat(jdbc.sql("SELECT COUNT(*) FROM local_calendar_event").query(Int::class.java).single()).isEqualTo(count)
        } finally {
            jdbc.sql("DROP TRIGGER reject_security_test_audit ON activity_event").update()
            jdbc.sql("DROP FUNCTION reject_security_test_audit()").update()
        }
        assertThat(authentication.register("audit_retry", OTHER_PASSWORD, invitation.code).user.username).isEqualTo("audit_retry")
    }

    @Test
    fun `viewer and ordinary users cannot administer identities and calendar`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val member = authentication.register("member", OTHER_PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        for (key in listOf("USER", "VIEWER")) {
            rbac.assignRoles(owner.user.id, member.user.id, setOf(rbac.roles(owner.user.id).single { it.key == key }.id))
            val header = "Bearer ${member.session.rawToken}"
            mockMvc.perform(get("/v1/rbac/users").header("Authorization", header)).andExpect(status().isForbidden)
            mockMvc.perform(get("/v1/calendar/events").header("Authorization", header)).andExpect(status().isForbidden)
            mockMvc.perform(put("/v1/rbac/users/${owner.user.id}/enabled?value=false").header("Authorization", header)).andExpect(status().isForbidden)
            mockMvc.perform(post("/v1/auth/invitations").header("Authorization", header)).andExpect(status().isForbidden)
        }
        assertThat(activity.recent(owner.user.id, 100).filter { it.eventType == "security.permission.denied" })
            .hasSize(8).allMatch { it.actorId == member.user.id.toString() && it.status == ActivityStatus.DENIED }
    }

    @Test
    fun `additive migration closes bootstrap on an existing V30 installation and preserves grants`() {
        val schema = "upgrade_" + UUID.randomUUID().toString().replace("-", "")
        java.sql.DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password).use { connection ->
            connection.createStatement().use { it.execute("CREATE SCHEMA $schema") }
            try {
                fun flyway(target: String?) = org.flywaydb.core.Flyway.configure()
                    .dataSource(postgres.jdbcUrl, postgres.username, postgres.password).schemas(schema).defaultSchema(schema)
                    .locations("classpath:db/migration").apply { if (target != null) target(target) }.load()
                flyway("30").migrate()
                connection.schema = schema
                val id = UUID.randomUUID()
                connection.prepareStatement("INSERT INTO user_account(id, username, password_hash, enabled, created_at, updated_at) VALUES (?, 'existing', 'test-only-hash', TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)").use {
                    it.setObject(1, id); it.executeUpdate()
                }
                val roleId = UUID.randomUUID()
                connection.prepareStatement("INSERT INTO rbac_role(id, installation_owner_id, role_key, display_name, system_role) VALUES (?, ?, 'USER', 'Restricted', TRUE)").use {
                    it.setObject(1, roleId); it.setObject(2, id); it.executeUpdate()
                }
                connection.prepareStatement("INSERT INTO rbac_role_permission(role_id, permission_key) VALUES (?, 'devices:read')").use {
                    it.setObject(1, roleId); it.executeUpdate()
                }
                val eventId = UUID.randomUUID()
                connection.prepareStatement("""INSERT INTO local_calendar_event(id,owner_id,title,starts_at,ends_at,time_zone,content_fingerprint,sync_to_google,created_at,updated_at)
                    VALUES(?,?,'Preserved event','2026-10-19T09:00:00Z','2026-10-19T10:00:00Z','Europe/Zurich','legacy',TRUE,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""").use {
                    it.setObject(1,eventId); it.setObject(2,id); it.executeUpdate()
                }
                val deviceId = UUID.randomUUID()
                connection.prepareStatement("""INSERT INTO integration_connection(id,owner_id,provider,display_name,endpoint_host,credential_ciphertext,credential_nonce,created_at,updated_at)
                    VALUES(?,?,'home_assistant','Preserved HA','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',decode('0102','hex'),decode('0304','hex'),CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""").use {
                    it.setObject(1,deviceId); it.setObject(2,id); it.executeUpdate()
                }
                connection.prepareStatement("INSERT INTO home_assistant_device(connection_id,owner_id,hardware_name,battery,capabilities) VALUES(?,?,'Sensor',NULL,'battery.read')").use {
                    it.setObject(1,deviceId); it.setObject(2,id); it.executeUpdate()
                }
                flyway(null).migrate()
                connection.createStatement().use { statement ->
                    statement.executeQuery("SELECT initialized FROM installation_bootstrap_state").use { it.next(); assertThat(it.getBoolean(1)).isTrue() }
                    statement.executeQuery("SELECT permission_key FROM rbac_role_permission").use { it.next(); assertThat(it.getString(1)).isEqualTo("devices:read"); assertThat(it.next()).isFalse() }
                    statement.executeQuery("SELECT COUNT(*) FROM user_account").use { it.next(); assertThat(it.getInt(1)).isEqualTo(1) }
                    statement.executeQuery("SELECT COUNT(*) FROM rbac_permission WHERE resource='calendar'").use { it.next(); assertThat(it.getInt(1)).isEqualTo(4) }
                    statement.executeQuery("SELECT title,sync_to_google,sync_status,google_event_id FROM local_calendar_event").use {
                        it.next(); assertThat(it.getString(1)).isEqualTo("Preserved event"); assertThat(it.getBoolean(2)).isTrue()
                        assertThat(it.getString(3)).isEqualTo("configuration_required"); assertThat(it.getString(4)).isNull()
                    }
                    statement.executeQuery("SELECT battery,brightness FROM home_assistant_device").use {
                        it.next(); assertThat(it.getObject(1)).isNull(); assertThat(it.getObject(2)).isNull()
                    }
                    statement.executeQuery("SELECT encode(credential_ciphertext,'hex') FROM integration_connection").use { it.next(); assertThat(it.getString(1)).isEqualTo("0102") }
                    statement.executeUpdate("DELETE FROM user_account")
                    statement.executeQuery("SELECT initialized FROM installation_bootstrap_state").use { it.next(); assertThat(it.getBoolean(1)).isTrue() }
                }
            } finally {
                connection.schema = "public"
                connection.createStatement().use { it.execute("DROP SCHEMA $schema CASCADE") }
            }
        }
    }

    @Test
    fun `google HTTP routes never use another workspace members private connection and audit writes`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val member = authentication.register("member", OTHER_PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        val role = rbac.createRole(owner.user.id, RoleRequest("calendar", "Calendar", setOf("calendar:read", "integrations:read")))
        rbac.assignRoles(owner.user.id, member.user.id, setOf(role.id))
        val authorization = google.authorize(owner.user.id)
        val state = java.net.URI(authorization.authorizationUrl).rawQuery.split("&").single { it.startsWith("state=") }.substringAfter("=")
        `when`(googleClient.exchange("code", "http://localhost.test/callback", "test-only-client", "test-only-secret"))
            .thenReturn(dev.kyrion.core.integration.GoogleToken("temporary-access", "temporary-refresh", Instant.now().plusSeconds(3600), "private@test.invalid"))
        google.complete(owner.user.id, "code", state)
        mockMvc.perform(get("/v1/integration-catalog/connections").header("Authorization", "Bearer ${member.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$").isEmpty)
        mockMvc.perform(get("/v1/devices").header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$").isEmpty)
        `when`(googleClient.rangedEvents((org.mockito.ArgumentMatchers.eq("temporary-access") ?: "temporary-access"), (org.mockito.ArgumentMatchers.eq("primary") ?: "primary"), org.mockito.ArgumentMatchers.anyString(), org.mockito.ArgumentMatchers.anyString())).thenReturn(dev.kyrion.core.integration.GoogleCalendarEvents(emptyList()))
        mockMvc.perform(get("/v1/integrations/google/calendar/events").header("Authorization", "Bearer ${member.session.rawToken}"))
            .andExpect(status().isConflict).andExpect(jsonPath("$.code").value("GOOGLE_DISCONNECTED"))
        mockMvc.perform(get("/v1/integrations/google").header("Authorization", "Bearer ${member.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$.connected").value(false))
        mockMvc.perform(get("/v1/integrations/google/calendar/events").header("Authorization", "Bearer ${owner.session.rawToken}"))
            .andExpect(status().isOk)
        `when`(googleClient.createEvent("temporary-access", dev.kyrion.core.integration.GoogleCalendarEventRequest("primary", "Private", "2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z")))
            .thenReturn(dev.kyrion.core.integration.GoogleCalendarEvent("provider-id", "Private", "2026-10-12T09:00:00Z", "2026-10-12T10:00:00Z"))
        mockMvc.perform(post("/v1/integrations/google/calendar/events").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content("""{"calendarId":"primary","summary":"Private","start":"2026-10-12T09:00:00Z","end":"2026-10-12T10:00:00Z"}"""))
            .andExpect(status().isOk)
        val events = activity.recent(owner.user.id, 100).filter { it.eventType == "google.calendar.event.created" }
        assertThat(events.map { it.status }).containsExactlyInAnyOrder(ActivityStatus.PROPOSED, ActivityStatus.SUCCEEDED)
        assertThat(events.map { it.correlationId }.distinct()).hasSize(1)
        assertThat(events).allMatch { it.actorId == owner.user.id.toString() && !it.summaryCode.contains("Private") }
    }

    @Test
    fun `calendar synchronization persists remote identity imports changes and confirms deletion through HTTP`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val header = "Bearer ${owner.session.rawToken}"
        val authorization = google.authorize(owner.user.id)
        val state = java.net.URI(authorization.authorizationUrl).rawQuery.split("&").single { it.startsWith("state=") }.substringAfter("=")
        `when`(googleClient.exchange("fixture-code", "http://localhost.test/callback", "test-only-client", "test-only-secret"))
            .thenReturn(dev.kyrion.core.integration.GoogleToken("fixture-access", "fixture-refresh", Instant.now().plusSeconds(3600), "fixture@test.invalid"))
        google.complete(owner.user.id, "fixture-code", state)
        `when`(googleClient.calendars("fixture-access")).thenReturn(dev.kyrion.core.integration.GoogleCalendars(listOf(
            dev.kyrion.core.integration.GoogleCalendar("fixture-calendar", "Fixture", "Europe/Zurich", "writer"))))
        val payload = """{"title":"Local appointment","startsAt":"2026-10-19T09:00:00Z","endsAt":"2026-10-19T10:00:00Z","timeZone":"Europe/Zurich","syncToGoogle":true,"googleCalendarId":"fixture-calendar"}"""
        val created = mockMvc.perform(post("/v1/calendar/events").header("Authorization", header).contentType(MediaType.APPLICATION_JSON).content(payload))
            .andExpect(status().isOk).andExpect(jsonPath("$.syncStatus").value("pending")).andReturn()
        val id = UUID.fromString(com.fasterxml.jackson.module.kotlin.jacksonObjectMapper().readTree(created.response.contentAsString).path("id").asText())
        val remoteId = id.toString().replace("-", "")
        var remote: dev.kyrion.core.integration.GoogleCalendarEvent? = null
        `when`(googleClient.getEvent("fixture-access", "fixture-calendar", remoteId)).thenAnswer {
            remote ?: throw dev.kyrion.core.integration.GoogleProviderException(404)
        }
        val write = dev.kyrion.core.integration.GoogleCalendarEventRequest("fixture-calendar", "Local appointment", "2026-10-19T09:00:00Z", "2026-10-19T10:00:00Z", id = remoteId)
        `when`(googleClient.createEvent("fixture-access", write)).thenAnswer {
            dev.kyrion.core.integration.GoogleCalendarEvent(remoteId, "Local appointment", write.start, write.end, "v1", kyrionId = remoteId).also { remote = it }
        }
        fun synchronize() = mockMvc.perform(post("/v1/calendar/sync").header("Authorization", header))
            .andExpect(status().isOk).andExpect(jsonPath("$.failed").value(0)).andExpect(jsonPath("$.conflicts").value(0))
        synchronize().andExpect(jsonPath("$.synchronized").value(1))
        synchronize()
        verify(googleClient, org.mockito.Mockito.times(1)).createEvent("fixture-access", write)
        mockMvc.perform(get("/v1/calendar/events").header("Authorization", header)).andExpect(status().isOk)
            .andExpect(jsonPath("$[0].googleEventId").value(remoteId)).andExpect(jsonPath("$[0].syncStatus").value("synced"))
        remote = remote!!.copy(summary = "Remote change", etag = "v2")
        synchronize()
        mockMvc.perform(get("/v1/calendar/events").header("Authorization", header)).andExpect(status().isOk)
            .andExpect(jsonPath("$[0].title").value("Remote change"))
            .andExpect(jsonPath("$[0].startsAt").value("2026-10-19T09:00:00Z"))
        mockMvc.perform(delete("/v1/calendar/events/$id").header("Authorization", header)).andExpect(status().isOk)
        assertThat(jdbc.sql("SELECT pending_deletion FROM local_calendar_event WHERE id=:id").param("id",id).query(Boolean::class.java).single()).isTrue()
        synchronize()
        verify(googleClient).removeEvent("fixture-access", "fixture-calendar", remoteId, "v2")
        assertThat(jdbc.sql("SELECT COUNT(*) FROM local_calendar_event WHERE id=:id").param("id",id).query(Int::class.java).single()).isZero()
        assertThat(activity.recent(owner.user.id,100).filter { it.eventType == "calendar.event.synchronized" }).isNotEmpty
    }

    @Test
    fun `calendar schedule is opt in durable leased and preserves rate limit backoff`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val actor = owner.user.id
        val repository = dev.kyrion.core.calendar.CalendarScheduleRepository(jdbc)
        assertThat(repository.get(actor).enabled).isFalse()
        assertThat(repository.claim(actor,true)).isNull()
        val lease = repository.claim(actor,false)!!
        assertThat(repository.claim(actor,false)).isNull()
        assertThat(repository.renew(actor,UUID.randomUUID())).isFalse()
        repository.finish(actor,lease,"GOOGLE_RATE_LIMITED",120)
        val failed = repository.get(actor)
        assertThat(failed.failureCount).isEqualTo(1)
        assertThat(failed.nextAttemptAt).isAfter(Instant.now().plusSeconds(110))
        repository.configure(actor,dev.kyrion.core.calendar.CalendarScheduleRequest(true,60))
        assertThat(repository.claim(actor,false)).isNull()
        assertThat(repository.due()).doesNotContain(actor)
        jdbc.sql("UPDATE calendar_sync_schedule SET next_attempt_at=CURRENT_TIMESTAMP - INTERVAL '1 second' WHERE actor_id=:actor").param("actor",actor).update()
        val next = repository.claim(actor,true)!!
        assertThat(repository.renew(actor,next)).isTrue()
        repository.finish(actor,lease,null)
        assertThat(repository.get(actor).running).isTrue()
        repository.finish(actor,next,null)
        assertThat(repository.get(actor).lastError).isNull()
        assertThat(repository.get(actor).lastSuccessAt).isNotNull()
        repository.suspend(actor)
        assertThat(repository.get(actor).enabled).isFalse()
        assertThat(repository.get(actor).lastError).isEqualTo("FORBIDDEN")
    }

    @Test
    fun `a blocked scheduled provider does not starve independent state refresh work`() {
        val entered=java.util.concurrent.CountDownLatch(1)
        val release=java.util.concurrent.CountDownLatch(1)
        val independent=java.util.concurrent.CountDownLatch(1)
        val slow=scheduler.schedule(Runnable { entered.countDown(); release.await(5,java.util.concurrent.TimeUnit.SECONDS) },Instant.now())
        try {
            assertThat(entered.await(2,java.util.concurrent.TimeUnit.SECONDS)).isTrue()
            val other=scheduler.schedule(Runnable { independent.countDown() },Instant.now())
            try { assertThat(independent.await(2,java.util.concurrent.TimeUnit.SECONDS)).isTrue() }
            finally { other?.cancel(true) }
        } finally { release.countDown(); slow?.cancel(true) }
    }

    @Test
    fun `concurrent delegated mutation waits for revoked permissions and fails closed`() {
        val owner = authentication.setup("owner", OLD_PASSWORD, setupSecret)
        val admin = authentication.register("admin", OTHER_PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        val role = rbac.roles(owner.user.id).single { it.key == "ADMIN" }
        rbac.assignRoles(owner.user.id, admin.user.id, setOf(role.id))
        val executor = java.util.concurrent.Executors.newSingleThreadExecutor()
        val started = java.util.concurrent.CountDownLatch(1)
        var future: java.util.concurrent.Future<Result<RoleView>>? = null
        try {
            transactions.executeWithoutResult {
                rbac.updateRole(owner.user.id, role.id, RoleRequest("ADMIN", "Admin", role.permissions - "roles:create"))
                future = executor.submit(java.util.concurrent.Callable {
                    started.countDown()
                    runCatching { rbac.createRole(admin.user.id, RoleRequest("late", "Late", setOf("devices:read"))) }
                })
                assertThat(started.await(5, java.util.concurrent.TimeUnit.SECONDS)).isTrue()
                assertThatThrownBy { future!!.get(200, java.util.concurrent.TimeUnit.MILLISECONDS) }.isInstanceOf(java.util.concurrent.TimeoutException::class.java)
            }
            assertThat(future!!.get(5, java.util.concurrent.TimeUnit.SECONDS).exceptionOrNull()).isInstanceOf(ForbiddenException::class.java)
            assertThat(rbac.roles(owner.user.id).map { it.key }).doesNotContain("late")
        } finally { executor.shutdownNow() }
    }

    @Test
    fun `failed owner setup transaction leaves bootstrap unconsumed for retry`() {
        assertThatThrownBy { transactions.executeWithoutResult {
            authentication.setup("rollback", OLD_PASSWORD, setupSecret)
            throw IllegalStateException("injected outer transaction failure")
        } }.isInstanceOf(IllegalStateException::class.java)
        assertThat(authentication.setupRequired()).isTrue()
        assertThat(jdbc.sql("SELECT COUNT(*) FROM user_account").query(Int::class.java).single()).isZero()
        assertThat(jdbc.sql("SELECT COUNT(*) FROM auth_session").query(Int::class.java).single()).isZero()
        assertThat(jdbc.sql("SELECT COUNT(*) FROM rbac_role").query(Int::class.java).single()).isZero()
        assertThat(authentication.setup("retry", OLD_PASSWORD, setupSecret).user.username).isEqualTo("retry")
    }

    @Test
    fun `AI preferences remain personal and policy administration requires existing RBAC`() {
        val token = setupToken()
        val actor = authentication.authenticate(token)!!.id
        val invite = authentication.createInvitation(token)
        val friend = authentication.register("AiFriend", OTHER_PASSWORD, invite.code)
        mockMvc.perform(
            put("/v1/ai/preferences").header("Authorization", "Bearer ${friend.session.rawToken}")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"chatProfileId":"test-local","monthlyTokenLimit":1000}""")
        )
            .andExpect(status().isOk).andExpect(jsonPath("$.localOnly").value(true))
        mockMvc.perform(get("/v1/ai/preferences").header("Authorization", "Bearer $token"))
            .andExpect(status().isOk).andExpect(jsonPath("$.preferences.chatProfileId").isEmpty)
        mockMvc.perform(
            put("/v1/ai/policy").header("Authorization", "Bearer ${friend.session.rawToken}")
                .contentType(MediaType.APPLICATION_JSON).content("""{"allowCloud":true}""")
        )
            .andExpect(status().isForbidden)
        mockMvc.perform(
            put("/v1/ai/policy").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"monthlyTokenLimit":500,"allowUserSelection":false}""")
        )
            .andExpect(status().isOk)
        assertThat(aiSettings.effectivePolicy(actor).monthlyTokenLimit).isEqualTo(500)
        mockMvc.perform(get("/v1/ai/usage")).andExpect(status().isUnauthorized)
        mockMvc.perform(
            put("/v1/ai/preferences").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON).content("""{"localOnly":"false"}""")
        )
            .andExpect(status().isBadRequest)
    }

    @Test
    fun `AI token reservations serialize concurrent requests and unknown prices fail closed`() {
        val token = setupToken();
        val actor = authentication.authenticate(token)!!.id
        aiSettings.savePolicy(actor, dev.kyrion.core.ai.AiPolicy(monthlyTokenLimit = 200))
        val ready = java.util.concurrent.CountDownLatch(1)
        val pool = java.util.concurrent.Executors.newFixedThreadPool(2)
        try {
            val jobs = (1..2).map {
                pool.submit<String> {
                    ready.await()
                    try {
                        aiUsage.reserve(
                            actor,
                            UUID.randomUUID(),
                            0,
                            aiGateway.model,
                            dev.kyrion.core.ai.AiRouteRequest(),
                            aiGateway.catalog(),
                            100
                        ); "reserved"
                    } catch (error: dev.kyrion.core.ai.AiFailure) {
                        error.code
                    }
                }
            }
            ready.countDown()
            assertThat(jobs.map {
                it.get(
                    20,
                    java.util.concurrent.TimeUnit.SECONDS
                )
            }).containsExactlyInAnyOrder("reserved", "TOKEN_BUDGET_EXCEEDED")
            assertThat(aiUsage.summary(actor).chargedTokens).isEqualTo(116)
        } finally {
            pool.shutdownNow()
        }
        aiSettings.savePolicy(
            actor,
            dev.kyrion.core.ai.AiPolicy(monthlyCostLimit = java.math.BigDecimal.ONE, currency = "CHF")
        )
        assertThatThrownBy {
            aiUsage.reserve(
                actor,
                UUID.randomUUID(),
                0,
                aiGateway.model,
                dev.kyrion.core.ai.AiRouteRequest(),
                aiGateway.catalog(),
                10
            )
        }
            .isInstanceOf(dev.kyrion.core.ai.AiFailure::class.java).hasMessage("COST_ESTIMATE_UNAVAILABLE")
    }

    @Test
    fun `AI generation observes usage server side prevents replay and uses actual local voice preference`() {
        val token = setupToken();
        val actor = authentication.authenticate(token)!!.id
        val conversation = UUID.randomUUID();
        val message = UUID.randomUUID()
        startHttpTurn(token, conversation, message, "Synthetic question", "2026-10-30T12:00:00Z")
        val alternate = aiGateway.model.copy(id = "voice-local")
        aiGateway.catalogValue = dev.kyrion.core.ai.AiCatalog(aiGateway.model.id, listOf(aiGateway.model, alternate))
        aiSettings.savePreferences(actor, dev.kyrion.core.ai.AiPreferences(voiceProfileId = alternate.id))
        val output = aiOrchestration.voice(actor, conversation, message, "en")
        assertThat(output).isEqualTo("Synthetic answer")
        assertThat(aiGateway.payloads.single()).contains("voice-local").doesNotContain("gemma3:1b")
        assertThat(aiUsage.summary(actor).chargedTokens).isEqualTo(14)
        assertThatThrownBy {
            aiOrchestration.voice(
                actor,
                conversation,
                message,
                "en"
            )
        }.hasMessage("REQUEST_ALREADY_STARTED")
        assertThat(aiGateway.payloads.size).isEqualTo(1)
    }

    @Test
    fun `AI fallback is audited and charged separately but partial output is never repeated`() {
        val token = setupToken();
        val actor = authentication.authenticate(token)!!.id
        val alternate = aiGateway.model.copy(id = "fallback-local")
        aiGateway.catalogValue = dev.kyrion.core.ai.AiCatalog(aiGateway.model.id, listOf(aiGateway.model, alternate))
        aiSettings.savePolicy(
            actor,
            dev.kyrion.core.ai.AiPolicy(allowFallback = true, fallbackProfiles = listOf(alternate.id))
        )
        aiSettings.savePreferences(actor, dev.kyrion.core.ai.AiPreferences(allowFallback = true))
        fun prepared(): dev.kyrion.core.ai.PreparedAiGeneration {
            val conversation = UUID.randomUUID();
            val message = UUID.randomUUID()
            startHttpTurn(token, conversation, message, "Synthetic request", "2026-10-30T12:00:00Z")
            return aiOrchestration.prepare(actor, dev.kyrion.core.ai.AiGenerationRequest(conversation, message))
        }
        aiGateway.behavior = { attempt, receive ->
            if (attempt == 1) receive("""{"type":"error","code":"MODEL_UNAVAILABLE"}""")
            else {
                receive("""{"type":"message.started","messageId":"m"}"""); receive("""{"type":"message.delta","messageId":"m","delta":"OK"}"""); receive(
                    """{"type":"message.completed","messageId":"m"}"""
                )
            }
        }
        val output = mutableListOf<String>(); aiOrchestration.stream(prepared(), output::add)
        assertThat(aiGateway.payloads.size).isEqualTo(2)
        assertThat(output.joinToString()).contains("routing.fallback")
        assertThat(
            jdbc.sql("SELECT COUNT(*) FROM ai_usage_attempt WHERE actor_id=:id").param("id", actor)
                .query(Int::class.java).single()
        ).isEqualTo(2)
        aiGateway.payloads.clear()
        aiGateway.behavior = { _, receive ->
            receive("""{"type":"message.delta","messageId":"m","delta":"Partial"}""")
            receive("""{"type":"error","code":"MODEL_UNAVAILABLE"}""")
        }
        aiOrchestration.stream(prepared()) {}
        assertThat(aiGateway.payloads.size).isEqualTo(1)
        assertThat(
            jdbc.sql("SELECT COUNT(*) FROM activity_event WHERE event_type='ai.route.fallback'").query(Int::class.java)
                .single()
        ).isEqualTo(1)
        for (code in listOf("REQUEST_TIMEOUT", "STREAM_FAILED", "TOOL_CALL_INVALID")) {
            aiGateway.payloads.clear()
            aiGateway.behavior = { _, receive -> receive("""{"type":"error","code":"$code"}""") }
            val events = mutableListOf<String>()
            aiOrchestration.stream(prepared(), events::add)
            assertThat(aiGateway.payloads.size).isEqualTo(1)
            assertThat(events.joinToString()).contains(code).doesNotContain("routing.fallback")
        }
        aiGateway.payloads.clear()
        aiGateway.behavior = { _, _ -> throw java.io.IOException("synthetic cancellation") }
        assertThatThrownBy { aiOrchestration.stream(prepared()) {} }.isInstanceOf(java.io.IOException::class.java)
        assertThat(aiGateway.payloads.size).isEqualTo(1)
        aiGateway.payloads.clear()
        aiGateway.behavior = { _, receive ->
            aiSettings.savePolicy(actor, dev.kyrion.core.ai.AiPolicy())
            receive("""{"type":"error","code":"MODEL_UNAVAILABLE"}""")
        }
        val revoked = mutableListOf<String>()
        aiOrchestration.stream(prepared(), revoked::add)
        assertThat(aiGateway.payloads.size).isEqualTo(1)
        assertThat(revoked.joinToString()).contains("ROUTE_CHANGED").doesNotContain("routing.fallback")
    }

    private fun startHttpTurn(token: String, conversationId: UUID, messageId: UUID, content: String, createdAt: String) {
        mockMvc.perform(
            post("/v1/conversations/$conversationId/turns").header("Authorization", "Bearer $token")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""{"title":"Lifecycle","tokenBudget":3072,"message":{"id":"$messageId","role":"user","content":"$content","createdAt":"$createdAt"}}"""),
        ).andExpect(status().isOk).andExpect(jsonPath("$.turnId").value(messageId.toString()))
    }

    private fun turnStatus(turnId: UUID): String = jdbc.sql("SELECT status FROM conversation_turn WHERE id = :id")
        .param("id", turnId).query(String::class.java).single()

    private fun setupToken(): String {
        val result = mockMvc.perform(
            post("/v1/auth/setup").header("X-Kyrion-Setup-Secret", setupSecret).contentType(MediaType.APPLICATION_JSON)
                .content("""{"username":"flo","password":"$OLD_PASSWORD"}"""),
        ).andExpect(status().isCreated).andReturn()
        return Regex("\"sessionToken\":\"([^\"]+)\"").find(result.response.contentAsString)!!.groupValues[1]
    }

    private fun insertAdditionalOwner(username: String): UUID {
        val id = UUID.randomUUID()
        val now = Timestamp.from(Instant.parse("2026-08-03T20:00:00Z"))
        jdbc.sql(
            "INSERT INTO user_account (id, username, password_hash, enabled, created_at, updated_at) VALUES (:id, :username, :hash, TRUE, :now, :now)",
        ).param("id", id).param("username", username).param("hash", passwordHashing.hash(OTHER_PASSWORD))
            .param("now", now).update()
        return id
    }

    companion object {
        private val setupSecret = SessionTokenService().create().rawToken
        private val bootstrapPath = Files.createTempFile("kyrion-bootstrap-test", ".secret").also { Files.writeString(it, setupSecret) }

        private const val OLD_PASSWORD = "old-secure-password"
        private const val NEW_PASSWORD = "new-secure-password"
        private const val OTHER_PASSWORD = "other-secure-password"
        private val auditKeyPath = Files.createTempDirectory("kyrion-audit-test").resolve("integrity.key").also {
            Files.write(it, ByteArray(32) { index -> (index + 1).toByte() })
        }.toString()
        private val credentialKeyPath = Path.of("$auditKeyPath.credentials").also {
            Files.write(it, ByteArray(32) { index -> (index + 33).toByte() })
        }

        @Container
        @JvmStatic
        val postgres = PostgreSQLContainer("postgres:17-alpine")

        @DynamicPropertySource
        @JvmStatic
        fun databaseProperties(registry: DynamicPropertyRegistry) {
            registry.add("kyrion.calendar.sync.scheduler-enabled") { "false" }
            registry.add("kyrion.home-assistant.refresh-enabled") { "false" }
            registry.add("kyrion.google.client-id") { "test-only-client" }
            registry.add("kyrion.google.client-secret") { "test-only-secret" }
            registry.add("kyrion.google.redirect-uri") { "http://localhost.test/callback" }
            registry.add("kyrion.security.bootstrap-secret-file") { bootstrapPath.toString() }
            registry.add("spring.datasource.url", postgres::getJdbcUrl)
            registry.add("spring.datasource.username", postgres::getUsername)
            registry.add("spring.datasource.password", postgres::getPassword)
            registry.add("kyrion.audit.integrity-key-file") { auditKeyPath }
            registry.add("kyrion.credentials.key-file") { credentialKeyPath.toString() }
        }
    }
}
