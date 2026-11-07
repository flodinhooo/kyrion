package dev.kyrion.core.security

import dev.kyrion.core.gateway.*
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.http.MediaType
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer
import java.nio.file.Files
import java.time.Instant
import java.util.UUID

@org.springframework.context.annotation.Import(dev.kyrion.core.ai.AiTestGatewayConfiguration::class)
@Testcontainers
@AutoConfigureMockMvc
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
class GatewayAuthorityIntegrationTest @Autowired constructor(
    private val jdbc: JdbcClient,
    private val gateways: GatewayService,
    private val queue: GatewayCommandService,
    private val rbac: RbacService,
    private val authorities: GatewayAuthorityService,
    private val mvc: MockMvc,
    private val sessions: AuthSessionService,
    private val executions: dev.kyrion.core.action.ActionExecutionService,
) {
    private lateinit var owner: UUID
    private lateinit var member: UUID
    private lateinit var node: UUID
    private lateinit var token: String
    private lateinit var target: UUID
    private lateinit var button: UUID
    private val address = "0x0011223344556677"
    private val buttonAddress = "0x0011223344556688"
    private val payload get() = mapOf<String, Any>("deviceId" to address, "on" to true)
    private val human get() = GatewayAuthority(owner, GatewayPrincipalKind.HUMAN, member, "devices:execute", "power.set")

    @BeforeEach fun prepare() {
        jdbc.sql("TRUNCATE user_account,activity_event,activity_integrity_chain CASCADE").update()
        owner = user()
        rbac.initializeUser(owner, owner, true)
        member = user(owner)
        rbac.initializeUser(member, owner, false)
        val enrollment = gateways.createEnrollment(owner, "Test node")
        val registered = gateways.enroll(enrollment.enrollmentToken, "test-node", "test", "Test", "1", "test")
        node = registered.node.id
        token = registered.gatewayToken
        // Synthetic observations only. No adapter or hardware is contacted.
        jdbc.sql("""UPDATE gateway_node SET last_seen_at=CURRENT_TIMESTAMP,health=CAST(:health AS jsonb) WHERE id=:node""")
            .param("node", node).param("health", """{"temperatureCelsius":30,"throttled":false,"memoryTotalBytes":100,"memoryAvailableBytes":50,
                "storageTotalBytes":100,"storageAvailableBytes":50,"ethernet":{"present":true,"connected":true},
                "wifi":{"present":false,"connected":false},"ipv6":true,"bluetooth":true,"systemState":"running",
                "adapters":[],"services":[],"zigbee":{"permitJoin":false,"channel":15,"devices":[
                {"ieeeAddress":"$address","friendlyName":"Lamp","vendor":"Test","model":"8720169364066","description":"Synthetic","supported":true},
                {"ieeeAddress":"$buttonAddress","friendlyName":"Button","vendor":"Test","model":"SNZB-01P","description":"Synthetic","supported":true}]}}""").update()
        target = connection(address)
        button = connection(buttonAddress)
    }

    @Test fun `valid member provenance survives enqueue claim and correlated completion without duplicate dispatch`() {
        val correlation = UUID.randomUUID()
        val id = queue.enqueue(human, node, "zigbee.power", payload, correlation)
        assertThat(jdbc.sql("SELECT authority->>'principalId' FROM gateway_command WHERE id=:id").param("id", id).query(String::class.java).single()).isEqualTo(member.toString())
        assertThat(queue.next(node, token)?.id).isEqualTo(id)
        assertThat(queue.next(node, token)).isNull()
        queue.complete(node, token, id, true, null)
        assertThat(queue.status(owner, id).status).isEqualTo("succeeded")
        assertThatThrownBy { queue.complete(node, token, id, true, null) }.isInstanceOf(GatewayCommandInvalidException::class.java)
        assertThat(jdbc.sql("SELECT count(*) FROM activity_event WHERE correlation_id=:id").param("id", correlation).query(Long::class.java).single()).isGreaterThanOrEqualTo(2)
    }

    @Test fun `role revocation after enqueue produces terminal denial and zero dispatch`() {
        val id = queue.enqueue(human, node, "zigbee.power", payload)
        jdbc.sql("DELETE FROM rbac_user_role WHERE user_id=:id").param("id", member).update()
        denied(id)
    }

    @Test fun `disabled member after enqueue produces zero dispatch`() {
        val id = queue.enqueue(human, node, "zigbee.power", payload)
        jdbc.sql("UPDATE user_account SET enabled=false WHERE id=:id").param("id", member).update()
        denied(id)
    }

    @Test fun `foreign and missing humans cannot enqueue even with a resource owner UUID`() {
        val foreign = user()
        for (actor in listOf(foreign, UUID.randomUUID())) {
            assertThatThrownBy { queue.enqueue(human.copy(principalId = actor), node, "zigbee.power", payload) }.isInstanceOf(ForbiddenException::class.java)
        }
        assertThat(queue.next(node, token)).isNull()
    }

    @Test fun `suspended Space blocks polling and never dispatches queued work`() {
        val id = queue.enqueue(human, node, "zigbee.power", payload)
        jdbc.sql("UPDATE kyrion_space SET status='SUSPENDED' WHERE id=:id").param("id", owner).update()
        assertThatThrownBy { queue.next(node, token) }.isInstanceOf(ForbiddenException::class.java)
        assertThat(queue.status(owner, id).status).isEqualTo("pending")
    }

    @Test fun `deleted target cannot be replaced by a new connection with the same address`() {
        val id = queue.enqueue(human, node, "zigbee.power", payload)
        jdbc.sql("DELETE FROM integration_connection WHERE id=:id").param("id", target).update()
        connection(address)
        denied(id)
    }

    @Test fun `target capability removed after enqueue denies dispatch`() {
        val id = queue.enqueue(human, node, "zigbee.power", payload)
        jdbc.sql("""UPDATE gateway_node SET health=jsonb_set(health,'{zigbee,devices,0,model}','"SNZB-03P"') WHERE id=:node""")
            .param("node", node).update()
        denied(id)
    }

    @Test fun `historical pending row without provenance is terminally denied without invented human`() {
        val id = UUID.randomUUID()
        jdbc.sql("""INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at)
            VALUES(:id,:node,:owner,'zigbee.power','{}','pending',CURRENT_TIMESTAMP)""")
            .param("id", id).param("node", node).param("owner", owner).update()
        denied(id, "AUTHORITY_PROVENANCE_MISSING")
    }

    @Test fun `legacy non object payload cannot prevent provenance denial or block the next command`() {
        val id = UUID.randomUUID()
        jdbc.sql("""INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at)
            VALUES(:id,:node,:owner,'zigbee.power','[]','pending',CURRENT_TIMESTAMP)""")
            .param("id", id).param("node", node).param("owner", owner).update()
        denied(id, "AUTHORITY_PROVENANCE_MISSING")
        val valid = queue.enqueue(human, node, "zigbee.power", payload)
        assertThat(queue.next(node, token)?.id).isEqualTo(valid)
    }

    @Test fun `cross node claim and completion cannot consume another nodes command`() {
        val enrollment = gateways.createEnrollment(owner, "Other node")
        val other = gateways.enroll(enrollment.enrollmentToken, "other-node", "test", "Test", "1", "test")
        val id = queue.enqueue(human, node, "zigbee.power", payload)
        assertThat(queue.next(other.node.id, other.gatewayToken)).isNull()
        assertThatThrownBy { queue.complete(other.node.id, other.gatewayToken, id, true, null) }.isInstanceOf(GatewayCommandInvalidException::class.java)
        assertThat(queue.next(node, token)?.id).isEqualTo(id)
        assertThatThrownBy { queue.complete(other.node.id, other.gatewayToken, id, true, null) }.isInstanceOf(GatewayCommandInvalidException::class.java)
    }

    @Test fun `foreign Space node cannot enqueue or claim commands from this Space`() {
        val foreign = user()
        rbac.initializeUser(foreign, foreign, true)
        val enrollment = gateways.createEnrollment(foreign, "Foreign")
        val other = gateways.enroll(enrollment.enrollmentToken, "foreign-node", "test", "Test", "1", "test")
        assertThatThrownBy { queue.enqueue(human, other.node.id, "zigbee.power", payload) }.isInstanceOf(ForbiddenException::class.java)
        val id = queue.enqueue(human, node, "zigbee.power", payload)
        assertThat(queue.next(other.node.id, other.gatewayToken)).isNull()
        assertThatThrownBy { queue.complete(other.node.id, other.gatewayToken, id, true, null) }.isInstanceOf(GatewayCommandInvalidException::class.java)
    }

    @Test fun `revoked automation grant denies queued command even when identical binding is recreated`() {
        val grant = grant()
        val id = queue.enqueue(automation(grant), node, "zigbee.power", payload)
        jdbc.sql("DELETE FROM zigbee_button_binding WHERE grant_id=:id").param("id", grant).update()
        grant()
        denied(id)
    }

    @Test fun `changed grant author permissions deny queued automation`() {
        val id = queue.enqueue(automation(grant()), node, "zigbee.power", payload)
        jdbc.sql("DELETE FROM rbac_user_role WHERE user_id=:id").param("id", member).update()
        denied(id)
    }

    @Test fun `room grant cannot dispatch a queued target that has left its authorized room`() {
        val room = UUID.randomUUID()
        jdbc.sql("""INSERT INTO owner_room(id,owner_id,name,created_at,updated_at)
            VALUES(:room,:owner,'Synthetic room',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
            .param("room", room).param("owner", owner).update()
        jdbc.sql("UPDATE integration_connection SET room_id=:room WHERE id=:target")
            .param("room", room).param("target", target).update()
        val id = queue.enqueue(automation(grant(room)), node, "zigbee.power", payload)
        jdbc.sql("UPDATE integration_connection SET room_id=NULL WHERE id=:target").param("target", target).update()
        denied(id)
    }

    @Test fun `automation cannot change target action capability or source node`() {
        val authority = automation(grant())
        assertThatThrownBy { queue.enqueue(authority, node, "zigbee.power", payload + ("on" to false)) }.isInstanceOf(ForbiddenException::class.java)
        assertThatThrownBy { queue.enqueue(authority.copy(sourceNodeId = UUID.randomUUID()), node, "zigbee.power", payload) }.isInstanceOf(ForbiddenException::class.java)
        assertThatThrownBy { queue.enqueue(authority.copy(capability = "light.setBrightness"), node, "zigbee.brightness", payload + ("brightness" to 10)) }.isInstanceOf(ForbiddenException::class.java)
        assertThatThrownBy { authorities.validateTarget(authority, button, true) }.isInstanceOf(ForbiddenException::class.java)
        assertThat(queue.next(node, token)).isNull()
    }

    @Test fun `valid automation dispatches as integration without human impersonation`() {
        val id = queue.enqueue(automation(grant()), node, "zigbee.power", payload)
        assertThat(queue.next(node, token)?.id).isEqualTo(id)
    }

    @Test fun `legacy automation without grant cannot enqueue`() {
        assertThatThrownBy { queue.enqueue(automation(null), node, "zigbee.power", payload) }.isInstanceOf(ForbiddenException::class.java)
        assertThat(queue.next(node, token)).isNull()
    }

    @Test fun `HTTP async device command captures member instead of resource owner and revocation denies dispatch`() {
        val credential = sessions.create(member).rawToken
        val response = mvc.perform(post("/v1/device-commands/async").header("Authorization", "Bearer $credential")
            .contentType(MediaType.APPLICATION_JSON).content("""{"capability":"power.set","selector":{"provider":"zigbee","deviceId":"$target"},"arguments":{"on":true}}"""))
            .andExpect(status().isAccepted).andReturn()
        assertThat(response.response.contentAsString).contains(target.toString())
        val id = jdbc.sql("SELECT id FROM gateway_command").query(UUID::class.java).single()
        assertThat(jdbc.sql("SELECT authority->>'principalId' FROM gateway_command").query(String::class.java).single()).isEqualTo(member.toString())
        jdbc.sql("DELETE FROM rbac_user_role WHERE user_id=:id").param("id", member).update()
        denied(id)
    }

    @Test fun `HTTP gateway entry requires live authentication and captures actual human`() {
        val credential = sessions.create(owner).rawToken
        mvc.perform(post("/v1/gateways/$node/zigbee/pairing").header("Authorization", "Bearer $credential")
            .contentType(MediaType.APPLICATION_JSON).content("""{"duration":20}""")).andExpect(status().isAccepted)
        assertThat(jdbc.sql("SELECT authority->>'principalId' FROM gateway_command").query(String::class.java).single()).isEqualTo(owner.toString())
        sessions.revoke(credential)
        mvc.perform(post("/v1/gateways/$node/zigbee/pairing").header("Authorization", "Bearer $credential")
            .contentType(MediaType.APPLICATION_JSON).content("""{"duration":20}""")).andExpect(status().isUnauthorized)
        // Logout blocks new ingress; previously accepted durable intent remains valid.
        assertThat(queue.next(node, token)).isNotNull()
        assertThat(queue.next(node, token)).isNull()
    }

    @Test fun `binding save issues fresh grants and identical resave revokes queued automation`() {
        val credential = sessions.create(owner).rawToken
        val body = """{"bindings":[{"gesture":"single","targetDeviceId":"$target","action":"turn_on"}]}"""
        fun save() = mvc.perform(put("/v1/devices/$button/button-bindings").header("Authorization", "Bearer $credential")
            .contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isOk)
        save()
        val grant = jdbc.sql("SELECT grant_id FROM zigbee_button_binding").query(UUID::class.java).single()
        val id = queue.enqueue(automation(grant), node, "zigbee.power", payload)
        save()
        assertThat(jdbc.sql("SELECT grant_id FROM zigbee_button_binding").query(UUID::class.java).single()).isNotEqualTo(grant)
        assertThat(jdbc.sql("""SELECT count(*) FROM activity_event WHERE correlation_id=:grant AND owner_id=:owner
            AND actor_id=:actor AND summary_code=:button AND event_type IN ('automation.grant.issued','automation.grant.revoked')""")
            .param("grant", grant).param("owner", owner).param("actor", owner.toString()).param("button", button.toString())
            .query(Long::class.java).single()).isEqualTo(2)
        denied(id)
    }

    @Test fun `explicit removal through binding API revokes pending command and releases no device payload`() {
        val credential = sessions.create(owner).rawToken
        val body = """{"bindings":[{"gesture":"single","targetDeviceId":"$target","action":"turn_on"}]}"""
        mvc.perform(put("/v1/devices/$button/button-bindings").header("Authorization", "Bearer $credential")
            .contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isOk)
        val grant = jdbc.sql("SELECT grant_id FROM zigbee_button_binding").query(UUID::class.java).single()
        val id = queue.enqueue(automation(grant), node, "zigbee.power", payload)
        mvc.perform(put("/v1/devices/$button/button-bindings").header("Authorization", "Bearer $credential")
            .contentType(MediaType.APPLICATION_JSON).content("""{"bindings":[]}""")).andExpect(status().isOk)
        assertThat(jdbc.sql("SELECT count(*) FROM zigbee_button_binding").query(Long::class.java).single()).isZero()
        denied(id)
    }

    @Test fun `automation traverses Action queue and confirmed result but revoked grant cannot replay cached success`() {
        val grant = grant()
        val context = dev.kyrion.core.action.ActionContext(owner,
            dev.kyrion.core.activity.ActivityActorType.INTEGRATION, button.toString(),
            dev.kyrion.core.action.InteractionChannel.AUTOMATION, java.util.Locale.ENGLISH,
            UUID.randomUUID(), UUID.randomUUID(), automationGrantId = grant, automationNodeId = node)
        val proposal = dev.kyrion.core.action.DeviceActionProposal(target, "power.set",
            dev.kyrion.core.capability.DeviceCommandArguments(on = true))
        val executor = java.util.concurrent.Executors.newSingleThreadExecutor()
        try {
            val outcome = executor.submit<dev.kyrion.core.action.ActionOutcome> { executions.execute(context, proposal) }
            var command: GatewayCommand? = null
            val deadline = System.nanoTime() + java.util.concurrent.TimeUnit.SECONDS.toNanos(10)
            while (command == null && System.nanoTime() < deadline && !outcome.isDone) {
                command = queue.next(node, token)
                if (command == null) Thread.sleep(25)
            }
            assertThat(command).isNotNull()
            queue.complete(node, token, command!!.id, true, null)
            assertThat(outcome.get(20, java.util.concurrent.TimeUnit.SECONDS).status)
                .isEqualTo(dev.kyrion.core.action.ActionOutcomeStatus.SUCCEEDED)
            jdbc.sql("DELETE FROM zigbee_button_binding WHERE grant_id=:id").param("id", grant).update()
            assertThatThrownBy { executions.execute(context, proposal) }.isInstanceOf(ForbiddenException::class.java)
            val renewed = grant()
            assertThatThrownBy { executions.execute(context.copy(automationGrantId = renewed), proposal) }
                .isInstanceOf(dev.kyrion.core.action.ActionIdempotencyMismatchException::class.java)
            assertThat(queue.next(node, token)).isNull()
        } finally { executor.shutdownNow() }
    }

    @Test fun `explicit retry retains original principal and revalidates revoked permissions`() {
        val id = queue.enqueue(human, node, "zigbee.power", payload)
        assertThat(queue.next(node, token)?.id).isEqualTo(id)
        // Simulate a future operator retry; production intentionally has no automatic replay.
        jdbc.sql("UPDATE gateway_command SET status='pending' WHERE id=:id").param("id", id).update()
        jdbc.sql("DELETE FROM rbac_user_role WHERE user_id=:id").param("id", member).update()
        denied(id)
    }

    @Test fun `concurrent claims release a command only once`() {
        val id = queue.enqueue(human, node, "zigbee.power", payload)
        val start = java.util.concurrent.CountDownLatch(1)
        val executor = java.util.concurrent.Executors.newFixedThreadPool(2)
        try {
            val results = (1..2).map { executor.submit<UUID?> { start.await(); queue.next(node, token)?.id } }
            start.countDown()
            assertThat(results.map { it.get(20, java.util.concurrent.TimeUnit.SECONDS) }).containsExactlyInAnyOrder(id, null)
        } finally { executor.shutdownNow() }
    }

    @Test fun `HOME voice uses satellite session authority and closed session denies dispatch`() {
        val (authority, session) = voice()
        val id = queue.enqueue(authority, node, "zigbee.power", payload)
        jdbc.sql("UPDATE voice_dialogue_session SET status='closed' WHERE id=:id").param("id", session).update()
        denied(id)
    }

    @Test fun `HOME voice live session can dispatch without claiming identified human authority`() {
        val (authority, _) = voice()
        val id = queue.enqueue(authority, node, "zigbee.power", payload)
        assertThat(queue.next(node, token)?.id).isEqualTo(id)
        assertThat(jdbc.sql("SELECT authority->>'kind' FROM gateway_command WHERE id=:id").param("id", id).query(String::class.java).single()).isEqualTo("HOME_VOICE")
    }

    @Test fun `expired foreign and missing Voice sessions cannot establish authority`() {
        val (authority, session) = voice()
        assertThatThrownBy { queue.enqueue(authority.copy(principalId = UUID.randomUUID()), node, "zigbee.power", payload) }.isInstanceOf(ForbiddenException::class.java)
        assertThatThrownBy { queue.enqueue(authority.copy(sessionId = null), node, "zigbee.power", payload) }.isInstanceOf(ForbiddenException::class.java)
        jdbc.sql("UPDATE voice_dialogue_session SET expires_at=:expiry WHERE id=:id")
            .param("expiry", java.sql.Timestamp.from(Instant.EPOCH)).param("id", session).update()
        assertThatThrownBy { queue.enqueue(authority, node, "zigbee.power", payload) }.isInstanceOf(ForbiddenException::class.java)
        assertThat(queue.next(node, token)).isNull()
    }

    @Test fun `Business Voice remains unavailable even with live satellite session`() {
        val (authority, _) = voice()
        jdbc.sql("UPDATE kyrion_space SET type='BUSINESS' WHERE id=:id").param("id", owner).update()
        assertThatThrownBy { queue.enqueue(authority, node, "zigbee.power", payload) }.isInstanceOf(IdentityPolicyException::class.java)
        assertThat(queue.next(node, token)).isNull()
    }

    @Test fun `V41 to V42 upgrade preserves legacy rows without manufacturing authority or grants`() {
        val schema = "gateway_upgrade_" + UUID.randomUUID().toString().replace("-", "")
        fun migration(target: String) = org.flywaydb.core.Flyway.configure()
            .dataSource(postgres.jdbcUrl, postgres.username, postgres.password)
            .schemas(schema).defaultSchema(schema).locations("classpath:db/migration").target(target).load()
        migration("41").migrate()
        java.sql.DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password).use { connection ->
            connection.schema = schema
            connection.createStatement().use { sql ->
                sql.execute("INSERT INTO user_account(id,username,password_hash) VALUES('$owner','upgrade-owner','fixture')")
                sql.execute("INSERT INTO gateway_node SELECT * FROM public.gateway_node WHERE id='$node'")
                sql.execute("INSERT INTO integration_connection SELECT * FROM public.integration_connection WHERE owner_id='$owner'")
                val command = UUID.randomUUID()
                sql.execute("""INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at,correlation_id)
                    VALUES('$command','$node','$owner','zigbee.power','{"deviceId":"$address","on":true}','pending',CURRENT_TIMESTAMP,'$command')""")
                sql.execute("""INSERT INTO zigbee_button_binding(owner_id,button_connection_id,gesture,target_connection_id,action,updated_at)
                    VALUES('$owner','$button','single','$target','turn_on',CURRENT_TIMESTAMP)""")
                fun history() = sql.executeQuery("SELECT string_agg(version||':'||checksum,',' ORDER BY installed_rank) FROM flyway_schema_history WHERE success AND version::int<=41").use {
                    it.next(); it.getString(1)
                }
                val before = history()
                migration("42").migrate()
                migration("42").validate()
                assertThat(history()).isEqualTo(before)
                sql.executeQuery("SELECT authority IS NULL AND status='pending' AND correlation_id=id AND payload->>'deviceId'='$address' FROM gateway_command WHERE id='$command'").use {
                    it.next(); assertThat(it.getBoolean(1)).isTrue()
                }
                sql.executeQuery("SELECT grant_id IS NULL AND granted_by IS NULL AND source_node_id IS NULL AND target_connection_id='$target' AND action='turn_on' FROM zigbee_button_binding").use {
                    it.next(); assertThat(it.getBoolean(1)).isTrue()
                }
            }
        }
    }

    private fun voice(): Pair<GatewayAuthority, UUID> {
        val satellite = UUID.randomUUID()
        val session = UUID.randomUUID()
        jdbc.sql("""INSERT INTO voice_satellite(id,owner_id,display_name,hostname,credential_hash,runtime_version,created_at,updated_at)
            VALUES(:id,:owner,'Synthetic','synthetic-voice',:hash,'test',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
            .param("id", satellite).param("owner", owner).param("hash", SessionTokenService().create().tokenHash).update()
        jdbc.sql("""INSERT INTO voice_dialogue_session(id,satellite_id,owner_id,conversation_id,status,started_at,last_activity_at,expires_at)
            VALUES(:id,:satellite,:owner,:conversation,'active',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP+INTERVAL '5 minutes')""")
            .param("id", session).param("satellite", satellite).param("owner", owner).param("conversation", UUID.randomUUID()).update()
        return GatewayAuthority(owner, GatewayPrincipalKind.HOME_VOICE, satellite, "devices:execute", "power.set", sessionId = session) to session
    }

    private fun denied(id: UUID, code: String = "AUTHORITY_REVOKED") {
        assertThat(queue.next(node, token)).isNull()
        assertThat(queue.status(owner, id)).isEqualTo(GatewayCommandStatus(id, "failed", code))
        assertThat(jdbc.sql("""SELECT EXISTS(SELECT 1 FROM activity_event e JOIN gateway_command c
            ON e.correlation_id=COALESCE(c.correlation_id,c.id) AND e.owner_id=c.owner_id
            WHERE c.id=:id AND e.event_type='gateway.command.denied' AND e.summary_code=:code
            AND e.actor_id IS NOT DISTINCT FROM (c.authority->>'principalId'))""")
            .param("id", id).param("code", code).query(Boolean::class.java).single()).isTrue()
        assertThat(queue.next(node, token)).isNull()
        assertThatThrownBy { queue.complete(node, token, id, true, null) }.isInstanceOf(GatewayCommandInvalidException::class.java)
    }

    private fun automation(grant: UUID?) = GatewayAuthority(owner, GatewayPrincipalKind.AUTOMATION, button,
        "devices:execute", "power.set", grantId = grant, sourceNodeId = node)

    private fun grant(room: UUID? = null): UUID {
        // USER deliberately lacks devices:update by default; grant only that bounded permission.
        val role = rbac.createRole(owner, RoleRequest("button_operator_${UUID.randomUUID()}", "Button operator", setOf("devices:update", "devices:execute")))
        rbac.assignRoles(owner, member, setOf(role.id))
        val id = UUID.randomUUID()
        jdbc.sql("""INSERT INTO zigbee_button_binding(owner_id,button_connection_id,gesture,target_connection_id,target_room_id,action,updated_at,grant_id,granted_by,source_node_id)
            VALUES(:owner,:button,'single',:target,:room,'turn_on',CURRENT_TIMESTAMP,:grant,:actor,:node)""")
            .param("owner", owner).param("button", button).param("target", if (room == null) target else null)
            .param("room", room).param("grant", id).param("actor", member).param("node", node).update()
        return id
    }

    private fun connection(address: String): UUID {
        val id = UUID.randomUUID()
        jdbc.sql("""INSERT INTO integration_connection(id,owner_id,provider,display_name,endpoint_host,credential_ciphertext,credential_nonce,created_at,updated_at)
            VALUES(:id,:owner,'zigbee','Test',:address,'','',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
            .param("id", id).param("owner", owner).param("address", address).update()
        return id
    }

    private fun user(space: UUID? = null): UUID {
        val id = UUID.randomUUID()
        jdbc.sql("""INSERT INTO user_account(id,username,password_hash,enabled,workspace_owner_id,created_at,updated_at)
            VALUES(:id,:name,'test-only-unused-hash',true,:space,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
            .param("id", id).param("name", "u_${id.toString().replace("-", "")}").param("space", space).update()
        return id
    }

    companion object {
        private val directory = Files.createTempDirectory("kyrion-gateway-authority-test")
        private val key = directory.resolve("key").also { Files.write(it, ByteArray(32) { (it + 1).toByte() }) }
        private val bootstrap = directory.resolve("bootstrap").also { Files.writeString(it, "test-only-bootstrap-secret") }
        @Container @JvmStatic val postgres = PostgreSQLContainer("postgres:17-alpine").withTmpFs(mapOf("/var/lib/postgresql/data" to "rw"))
        @DynamicPropertySource @JvmStatic fun properties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url", postgres::getJdbcUrl)
            registry.add("spring.datasource.username", postgres::getUsername)
            registry.add("spring.datasource.password", postgres::getPassword)
            registry.add("kyrion.security.bootstrap-secret-file") { bootstrap.toString() }
            registry.add("kyrion.audit.integrity-key-file") { key.toString() }
            registry.add("kyrion.credentials.key-file") { key.toString() }
            registry.add("kyrion.knowledge.worker-enabled") { "false" }
            registry.add("kyrion.calendar.sync.scheduler-enabled") { "false" }
            registry.add("kyrion.home-assistant.refresh-enabled") { "false" }
        }
    }
}
