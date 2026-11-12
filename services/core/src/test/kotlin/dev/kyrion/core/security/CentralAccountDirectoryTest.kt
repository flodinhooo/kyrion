package dev.kyrion.core.security

import dev.kyrion.core.integration.CredentialCipher
import org.assertj.core.api.Assertions.*
import org.junit.jupiter.api.Test
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.test.context.DynamicPropertyRegistry
import org.springframework.test.context.DynamicPropertySource
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer
import java.nio.file.Files
import java.time.Instant
import java.util.UUID
import java.net.InetSocketAddress
import com.sun.net.httpserver.HttpServer
import java.util.concurrent.CopyOnWriteArrayList

@org.springframework.context.annotation.Import(dev.kyrion.core.ai.AiTestGatewayConfiguration::class)
@Testcontainers
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
class CentralAccountDirectoryTest @Autowired constructor(
    private val authentication: LocalAuthenticationService,
    private val jdbc: JdbcClient,
    private val proofs: CentralProofCache,
    private val cipher: CredentialCipher,
    private val directory: CentralAccountDirectory,
) {
    @Test
    fun `verified profiles are user scoped and encrypted receipts revoke only their directory row`() {
        val owner = authentication.setup("directory-owner", PASSWORD, setupSecret)
        val member = authentication.register(
            "directory-member",
            PASSWORD,
            authentication.createInvitation(owner.session.rawToken).code
        )
        val subject = "verified-central-user"
        jdbc.sql("INSERT INTO central_identity_link(user_id,issuer,subject,linked_at) VALUES(:user,:issuer,:subject,CURRENT_TIMESTAMP)")
            .param("user", owner.user.id).param("issuer", ISSUER).param("subject", subject).update()
        jdbc.sql("INSERT INTO central_identity_link(user_id,issuer,subject,linked_at) VALUES(:user,:issuer,'another-central-user',CURRENT_TIMESTAMP)")
            .param("user", member.user.id).param("issuer", ISSUER).update()
        proofs.remember(
            CentralDisplayProof(
                ISSUER,
                subject,
                "owner@directory.test",
                "Directory Owner",
                "short-lived-provider-proof",
                Instant.now().plusSeconds(300)
            )
        )
        directory.synchronize()
        assertThat(directory.account(owner.session.rawToken).account?.email).isEqualTo("owner@directory.test")
        assertThat(directory.account(member.session.rawToken).account).isNull()
        assertThatThrownBy { directory.account("invalid-session") }.isInstanceOf(UnauthenticatedException::class.java)
        val requests = CopyOnWriteArrayList<Pair<String, String>>()
        val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        val receipt = SessionTokenService().create().rawToken
        val id = UUID.randomUUID()
        server.createContext("/api/account/installations/report") { exchange ->
            requests.add(exchange.requestMethod to exchange.requestHeaders.getFirst("Authorization"))
            exchange.requestBody.readAllBytes()
            if (exchange.requestMethod == "POST") {
                val body = """{"id":"$id","credential":"$receipt"}""".toByteArray()
                exchange.sendResponseHeaders(201, body.size.toLong()); exchange.responseBody.use { it.write(body) }
            } else {
                exchange.sendResponseHeaders(204, -1); exchange.close()
            }
        }
        server.start()
        try {
            val sync = CentralAccountDirectory(
                jdbc,
                authentication,
                proofs,
                cipher,
                ISSUER,
                "http://127.0.0.1:${server.address.port}",
                true
            )
            sync.synchronize()
            assertThat(requests.single()).isEqualTo("POST" to "Bearer short-lived-provider-proof")
            val ciphertext = jdbc.sql("SELECT credential_ciphertext FROM central_account_profile WHERE user_id=:user")
                .param("user", owner.user.id).query(ByteArray::class.java).single()
            assertThat(String(ciphertext)).doesNotContain(receipt).doesNotContain("short-lived-provider-proof")
            assertThat(sync.account(owner.session.rawToken).directoryState).isEqualTo("confirmed")
            jdbc.sql("DELETE FROM central_identity_link WHERE user_id=:user").param("user", owner.user.id).update()
            jdbc.sql("UPDATE central_account_profile SET last_attempt_at=CURRENT_TIMESTAMP-interval '1 minute'")
                .update()
            sync.synchronize()
            assertThat(requests.last()).isEqualTo("DELETE" to "Bearer $receipt")
            assertThat(sync.account(owner.session.rawToken).linked).isFalse()
            assertThat(
                jdbc.sql("SELECT count(*) FROM central_account_profile WHERE user_id=:user")
                    .param("user", owner.user.id).query(Int::class.java).single()
            ).isZero()
        } finally {
            server.stop(0)
        }
    }

    companion object {
        private const val PASSWORD = "directory-local-password-123"
        private const val ISSUER = "https://directory.test/realms/kyrion"
        private val setupSecret = SessionTokenService().create().rawToken
        private val bootstrap =
            Files.createTempFile("directory-bootstrap", ".secret").also { Files.writeString(it, setupSecret) }
        private val key =
            Files.createTempFile("directory-key", ".key").also { Files.write(it, ByteArray(32) { (it + 1).toByte() }) }
        @Container
        @JvmStatic
        val postgres = PostgreSQLContainer("postgres:17-alpine").withTmpFs(mapOf("/var/lib/postgresql/data" to "rw"))
            .withEnv("POSTGRES_INITDB_ARGS", "--no-sync")

        @DynamicPropertySource
        @JvmStatic
        fun properties(r: DynamicPropertyRegistry) {
            r.add("spring.datasource.url", postgres::getJdbcUrl); r.add(
                "spring.datasource.username",
                postgres::getUsername
            ); r.add("spring.datasource.password", postgres::getPassword)
            r.add("kyrion.credentials.key-file") { key.toString() }; r.add("kyrion.audit.integrity-key-file") { key.toString() }; r.add(
                "kyrion.security.bootstrap-secret-file"
            ) { bootstrap.toString() }
            r.add("spring.config.import") { "" }; r.add("KYRION_CENTRAL_ISSUER") { ISSUER }; r.add("KYRION_ACCOUNT_DIRECTORY_ORIGIN") { "" }
            r.add("kyrion.knowledge.root") { Files.createTempDirectory("directory-knowledge").toString() }
        }
    }
}
