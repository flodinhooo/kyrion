package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.BeforeEach
import org.junit.jupiter.api.Test
import org.mockito.Mockito.*
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.*
import org.springframework.http.MediaType
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer
import java.nio.file.Files
import java.time.Instant
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class IdentityTestClock : java.time.Clock() {
    @Volatile var now: Instant = Instant.now()
    override fun getZone(): java.time.ZoneId = java.time.ZoneOffset.UTC
    override fun withZone(zone: java.time.ZoneId): java.time.Clock = this
    override fun instant(): Instant = now
}

@org.springframework.boot.test.context.TestConfiguration
class UnifiedIdentityClockConfiguration {
    @org.springframework.context.annotation.Bean
    fun identityTestClock() = IdentityTestClock()
}

@org.springframework.context.annotation.Import(dev.kyrion.core.ai.AiTestGatewayConfiguration::class, UnifiedIdentityClockConfiguration::class)
@Testcontainers
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@AutoConfigureMockMvc
class UnifiedIdentityIntegrationTest @Autowired constructor(
    private val authentication: LocalAuthenticationService,
    private val identities: UnifiedIdentityService,
    private val jdbc: JdbcClient,
    private val rbac: RbacService,
    private val mockMvc: MockMvc,
    private val testClock: IdentityTestClock,
) {
    @MockitoBean lateinit var provider: CentralIdentityProvider

    @BeforeEach fun resetDatabase() {
        testClock.now = Instant.now()
        jdbc.sql("TRUNCATE TABLE user_account, activity_event, activity_integrity_chain CASCADE").update()
        jdbc.sql("UPDATE installation_bootstrap_state SET initialized=FALSE").update()
        `when`(provider.available()).thenReturn(true)
        `when`(provider.startDevice()).thenReturn(DeviceAuthorization("secret-device-code", "USER-CODE", "https://identity.example/device", 600, 1))
        `when`(provider.pollDevice(anyString())).thenReturn(ConfirmedCentralIdentity(ISSUER, "subject-a", Instant.now().plusSeconds(600)))
    }

    @Test fun `local authentication needs no central provider and existing credentials stay intact`() {
        val owner = owner()
        val hash = jdbc.sql("SELECT password_hash FROM user_account WHERE id=:id").param("id", owner.user.id).query(String::class.java).single()
        `when`(provider.available()).thenReturn(false)
        `when`(provider.startDevice()).thenThrow(CentralIdentityException("CENTRAL_UNAVAILABLE"))
        assertThat(authentication.login("flo", PASSWORD).user.id).isEqualTo(owner.user.id)
        assertThat(authentication.authenticate(owner.session.rawToken)?.id).isEqualTo(owner.user.id)
        assertThat(identities.status(owner.session.rawToken).linked).isFalse()
        assertThat(jdbc.sql("SELECT password_hash FROM user_account WHERE id=:id").param("id", owner.user.id).query(String::class.java).single()).isEqualTo(hash)
        verify(provider, never()).pollDevice(anyString())
        verify(provider, never()).startDevice()
    }

    @Test fun `additive V44 upgrade preserves local credential session membership and bootstrap`() {
        val schema = "identity_upgrade_" + java.util.UUID.randomUUID().toString().replace("-", "")
        fun flyway(target: String? = null) = org.flywaydb.core.Flyway.configure()
            .dataSource(postgres.jdbcUrl, postgres.username, postgres.password)
            .schemas(schema).defaultSchema(schema).locations("classpath:db/migration")
            .apply { if (target != null) target(target) }.load()
        flyway("41").migrate()
        val id = java.util.UUID.randomUUID()
        java.sql.DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password).use { connection ->
            connection.schema = schema
            connection.createStatement().use { sql ->
                sql.execute("INSERT INTO user_account(id,username,password_hash) VALUES('$id','existing','unchanged-argon2-hash')")
                sql.execute("UPDATE installation_bootstrap_state SET initialized=TRUE")
                sql.execute("INSERT INTO auth_session(id,user_id,token_hash,expires_at) VALUES(gen_random_uuid(),'$id',repeat('c',64),CURRENT_TIMESTAMP+INTERVAL '1 day')")
                sql.execute("INSERT INTO rbac_role(id,installation_owner_id,role_key,display_name,system_role) VALUES('$id','$id','OWNER','Owner',TRUE)")
                sql.execute("INSERT INTO rbac_user_role(user_id,role_id) VALUES('$id','$id')")
            }
            flyway().migrate()
            flyway().validate()
            connection.createStatement().use { sql ->
                sql.executeQuery("SELECT password_hash,space_id FROM user_account WHERE id='$id'").use { result ->
                    result.next(); assertThat(result.getString(1)).isEqualTo("unchanged-argon2-hash"); assertThat(result.getObject(2)).isEqualTo(id)
                }
                for ((query, expected) in listOf("SELECT COUNT(*) FROM auth_session WHERE revoked_at IS NULL" to 1,
                    "SELECT COUNT(*) FROM rbac_user_role WHERE user_id='$id' AND role_id='$id'" to 1,
                    "SELECT COUNT(*) FROM installation_bootstrap_state WHERE initialized" to 1,
                    "SELECT COUNT(*) FROM central_identity_link" to 0)) {
                    sql.executeQuery(query).use { result -> result.next(); assertThat(result.getInt(1)).isEqualTo(expected) }
                }
            }
        }
    }

    @Test fun `link requires local password central proof and explicit confirmation without role changes`() {
        val owner = owner()
        val member = authentication.register("member", PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        val permissions = rbac.permissions(member.user.id)
        assertThatThrownBy { identities.start("LINK", member.session.rawToken, "wrong-password") }.isInstanceOf(InvalidCurrentPasswordException::class.java)
        val start = identities.start("LINK", member.session.rawToken, PASSWORD)
        assertThatThrownBy { identities.complete(start.operationToken, member.session.rawToken, true) }.isInstanceOf(CentralIdentityException::class.java)
        assertThat(poll(start.operationToken, member.session.rawToken).status).isEqualTo("CONFIRM")
        assertThatThrownBy { identities.complete(start.operationToken, member.session.rawToken, false) }.isInstanceOf(CentralIdentityException::class.java)
        assertThat(identities.complete(start.operationToken, member.session.rawToken, true)).isNull()
        assertThat(identities.status(member.session.rawToken)).isEqualTo(CentralLinkStatus(true, ISSUER))
        assertThat(rbac.permissions(member.user.id)).isEqualTo(permissions)
        assertThat(jdbc.sql("SELECT COUNT(*) FROM user_account").query(Long::class.java).single()).isEqualTo(2)
        assertThatThrownBy { identities.complete(start.operationToken, member.session.rawToken, true) }.isInstanceOf(CentralIdentityException::class.java)
    }

    @Test fun `operation is bound to original session and cannot be reused after revocation`() {
        val owner = owner()
        val start = identities.start("LINK", owner.session.rawToken, PASSWORD)
        val anotherSession = authentication.login("flo", PASSWORD)
        assertThatThrownBy { poll(start.operationToken, anotherSession.session.rawToken) }.isInstanceOf(CentralIdentityException::class.java)
        assertThatThrownBy { poll(start.operationToken, null) }.isInstanceOf(CentralIdentityException::class.java)
        authentication.logout(owner.session.rawToken, owner.user.id)
        assertThatThrownBy { poll(start.operationToken, owner.session.rawToken) }.isInstanceOf(UnauthenticatedException::class.java)
    }

    @Test fun `central proof without mapping does not create account or owner and email is irrelevant`() {
        val owner = owner()
        // Provider proof has no email matching input at all: only issuer and subject are accepted.
        val start = identities.start("LOGIN", null, null)
        poll(start.operationToken, null)
        assertThatThrownBy { identities.complete(start.operationToken, null, true) }.isInstanceOf(CentralIdentityException::class.java)
            .extracting("code").isEqualTo("SPACE_ACCESS_REQUIRED")
        assertThat(jdbc.sql("SELECT COUNT(*) FROM user_account").query(Long::class.java).single()).isEqualTo(1)
        assertThat(identities.status(owner.session.rawToken).linked).isFalse()
    }

    @Test fun `central sessions are bounded use existing permissions and offline requests do not contact provider`() {
        val owner = owner()
        val member = authentication.register("member", PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        link(member)
        val start = identities.start("LOGIN", null, null)
        poll(start.operationToken, null)
        val loggedIn = requireNotNull(identities.complete(start.operationToken, null, true))
        assertThat(loggedIn.user.id).isEqualTo(member.user.id)
        assertThat(loggedIn.session.session.expiresAt).isBeforeOrEqualTo(Instant.now().plusSeconds(900))
        clearInvocations(provider)
        assertThat(authentication.authenticate(loggedIn.session.rawToken)?.id).isEqualTo(member.user.id)
        verifyNoInteractions(provider)
        assertThat(rbac.permissions(loggedIn.user.id)).isEqualTo(rbac.permissions(member.user.id))
        jdbc.sql("UPDATE auth_session SET expires_at=created_at-INTERVAL '1 second',created_at=created_at-INTERVAL '1 hour' WHERE id=:id")
            .param("id", loggedIn.session.session.id).update()
        assertThat(authentication.authenticate(loggedIn.session.rawToken)).isNull()
    }

    @Test fun `unlink requires password revokes central sessions and preserves last owner local access`() {
        val owner = owner()
        link(owner)
        val start = identities.start("LOGIN", null, null)
        poll(start.operationToken, null)
        val central = requireNotNull(identities.complete(start.operationToken, null, true))
        assertThatThrownBy { identities.unlink(owner.session.rawToken, "wrong-password") }.isInstanceOf(InvalidCurrentPasswordException::class.java)
        identities.unlink(owner.session.rawToken, PASSWORD)
        assertThat(identities.status(owner.session.rawToken).linked).isFalse()
        assertThat(authentication.authenticate(central.session.rawToken)).isNull()
        assertThat(authentication.authenticate(owner.session.rawToken)?.id).isEqualTo(owner.user.id)
        assertThat(authentication.login("flo", PASSWORD).user.id).isEqualTo(owner.user.id)
        assertThat(rbac.users(owner.user.id).single().roles).contains("OWNER")
    }

    @Test fun `concurrent links of one identity have exactly one winner`() {
        val owner = owner()
        val member = authentication.register("member", PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        val operations = listOf(owner, member).map { account ->
            identities.start("LINK", account.session.rawToken, PASSWORD).also { poll(it.operationToken, account.session.rawToken) }
        }
        val start = CountDownLatch(1)
        val executor = Executors.newFixedThreadPool(2)
        try {
            val futures = listOf(owner, member).mapIndexed { index, account -> executor.submit<Boolean> {
                start.await()
                try { identities.complete(operations[index].operationToken, account.session.rawToken, true); true }
                catch (_: CentralIdentityException) { false }
            } }
            start.countDown()
            assertThat(futures.map { it.get(20, TimeUnit.SECONDS) }).containsExactlyInAnyOrder(true, false)
        } finally { executor.shutdownNow() }
        assertThat(jdbc.sql("SELECT COUNT(*) FROM central_identity_link").query(Long::class.java).single()).isEqualTo(1)
    }

    @Test fun `proof expiring while confirmation waits for database lock cannot link`() {
        val owner = owner()
        val start = identities.start("LINK", owner.session.rawToken, PASSWORD)
        poll(start.operationToken, owner.session.rawToken)
        val executor = Executors.newSingleThreadExecutor()
        java.sql.DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password).use { blocker ->
            blocker.autoCommit = false
            blocker.createStatement().use { it.execute("SELECT pg_advisory_xact_lock(5544332211)") }
            try {
                val result = executor.submit<Boolean> {
                    try { identities.complete(start.operationToken, owner.session.rawToken, true); true }
                    catch (_: CentralIdentityException) { false }
                }
                val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
                while (jdbc.sql("SELECT COUNT(*) FROM pg_locks WHERE locktype='advisory' AND NOT granted").query(Long::class.java).single() == 0L) {
                    check(System.nanoTime() < deadline) { "Confirmation did not reach the serialization lock" }
                    Thread.sleep(10)
                }
                testClock.now = testClock.now.plusSeconds(700)
                blocker.commit()
                assertThat(result.get(10, TimeUnit.SECONDS)).isFalse()
                assertThat(identities.status(owner.session.rawToken).linked).isFalse()
            } finally { blocker.rollback(); executor.shutdownNow() }
        }
    }

    @Test fun `local suspension and session logout remain authoritative for linked identities`() {
        val owner = owner()
        val member = authentication.register("member", PASSWORD, authentication.createInvitation(owner.session.rawToken).code)
        link(member)
        val start = identities.start("LOGIN", null, null)
        poll(start.operationToken, null)
        val central = requireNotNull(identities.complete(start.operationToken, null, true))
        authentication.logout(central.session.rawToken, member.user.id)
        assertThat(authentication.authenticate(central.session.rawToken)).isNull()
        jdbc.sql("UPDATE user_account SET enabled=FALSE WHERE id=:id").param("id", member.user.id).update()
        val next = identities.start("LOGIN", null, null)
        poll(next.operationToken, null)
        assertThatThrownBy { identities.complete(next.operationToken, null, true) }.isInstanceOf(ForbiddenException::class.java)
    }

    @Test fun `cancelled operations and expired confirmed tokens cannot complete`() {
        val owner = owner()
        val start = identities.start("LINK", owner.session.rawToken, PASSWORD)
        identities.cancel(start.operationToken, owner.session.rawToken)
        assertThatThrownBy { poll(start.operationToken, owner.session.rawToken) }.isInstanceOf(CentralIdentityException::class.java)
        val expired = identities.start("LINK", owner.session.rawToken, PASSWORD)
        `when`(provider.pollDevice(anyString())).thenReturn(ConfirmedCentralIdentity(ISSUER, "subject-a", Instant.now().minusSeconds(1)))
        assertThatThrownBy { poll(expired.operationToken, owner.session.rawToken) }.isInstanceOf(CentralIdentityException::class.java)
        assertThat(identities.status(owner.session.rawToken).linked).isFalse()
    }

    @Test fun `HTTP polling and cancellation accept operation only while completion requires explicit confirmation`() {
        val owner = owner()
        val start = identities.start("LINK", owner.session.rawToken, PASSWORD)
        testClock.now = testClock.now.plusSeconds(2)
        mockMvc.perform(post("/v1/auth/central/poll").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content("""{"operationToken":"${start.operationToken}"}"""))
            .andExpect(status().isOk).andExpect(jsonPath("$.status").value("CONFIRM"))
        mockMvc.perform(post("/v1/auth/central/complete").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content("""{"operationToken":"${start.operationToken}"}"""))
            .andExpect(status().isBadRequest)
        for (invalid in listOf("null", "false", "\"true\"", "1", "{}", "[]")) {
            mockMvc.perform(post("/v1/auth/central/complete").header("Authorization", "Bearer ${owner.session.rawToken}")
                .contentType(MediaType.APPLICATION_JSON).content("""{"operationToken":"${start.operationToken}","confirm":$invalid}"""))
                .andExpect(status().isBadRequest)
        }
        mockMvc.perform(post("/v1/auth/central/complete").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content("""{"operationToken":"${start.operationToken}","confirm":true}"""))
            .andExpect(status().isOk).andExpect(jsonPath("$.linked").value(true))
        val cancel = identities.start("LOGIN", null, null)
        mockMvc.perform(post("/v1/auth/central/cancel").contentType(MediaType.APPLICATION_JSON)
            .content("""{"operationToken":"${cancel.operationToken}"}"""))
            .andExpect(status().isNoContent)
    }

    @Test fun `HTTP rejects malformed operations requires authentication and never exposes device secret`() {
        val owner = owner()
        mockMvc.perform(get("/v1/auth/central/config")).andExpect(status().isOk).andExpect(jsonPath("$.enabled").value(true))
        mockMvc.perform(get("/v1/auth/central/status")).andExpect(status().isUnauthorized)
        mockMvc.perform(post("/v1/auth/central/start").contentType(MediaType.APPLICATION_JSON).content("""{"mode":"LINK","currentPassword":"$PASSWORD"}"""))
            .andExpect(status().isUnauthorized)
        mockMvc.perform(post("/v1/auth/central/poll").contentType(MediaType.APPLICATION_JSON).content("""{"operationToken":"invalid"}"""))
            .andExpect(status().isBadRequest)
        val result = mockMvc.perform(post("/v1/auth/central/start").header("Authorization", "Bearer ${owner.session.rawToken}")
            .contentType(MediaType.APPLICATION_JSON).content("""{"mode":"LINK","currentPassword":"$PASSWORD"}"""))
            .andExpect(status().isOk).andExpect(header().string("Cache-Control", "no-store")).andReturn()
        assertThat(result.response.contentAsString).doesNotContain("secret-device-code", "passwordHash", "subject-a")
    }

    private fun poll(token: String, session: String?): CentralPollStatus {
        testClock.now = testClock.now.plusSeconds(2)
        return identities.poll(token, session)
    }
    private fun owner() = authentication.setup("flo", PASSWORD, setupSecret)
    private fun link(account: AuthenticatedOwner) {
        val start = identities.start("LINK", account.session.rawToken, PASSWORD)
        poll(start.operationToken, account.session.rawToken)
        identities.complete(start.operationToken, account.session.rawToken, true)
    }

    companion object {
        private const val PASSWORD = "local-test-password-123"
        private const val ISSUER = "https://identity.example/realms/kyrion"
        private val setupSecret = SessionTokenService().create().rawToken
        private val bootstrapPath = Files.createTempFile("unified-bootstrap", ".secret").also { Files.writeString(it, setupSecret) }
        private val auditPath = Files.createTempFile("unified-audit", ".key").also { Files.write(it, ByteArray(32) { (it + 1).toByte() }) }
        @Container @JvmStatic val postgres = PostgreSQLContainer("postgres:17-alpine").withTmpFs(mapOf("/var/lib/postgresql/data" to "rw"))
            .withEnv("POSTGRES_INITDB_ARGS", "--no-sync")
            .withStartupTimeout(java.time.Duration.ofMinutes(3))
        @DynamicPropertySource @JvmStatic fun properties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url", postgres::getJdbcUrl)
            registry.add("spring.datasource.username", postgres::getUsername)
            registry.add("spring.datasource.password", postgres::getPassword)
            registry.add("kyrion.audit.integrity-key-file") { auditPath.toString() }
            registry.add("kyrion.credentials.key-file") { auditPath.toString() }
            registry.add("kyrion.security.bootstrap-secret-file") { bootstrapPath.toString() }
            registry.add("kyrion.knowledge.worker-enabled") { "false" }
            registry.add("kyrion.calendar.sync.scheduler-enabled") { "false" }
            registry.add("kyrion.home-assistant.refresh-enabled") { "false" }
        }
    }
}
