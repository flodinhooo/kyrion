package dev.kyrion.core.security

import dev.kyrion.core.conversation.Conversation
import dev.kyrion.core.conversation.ConversationMessage
import dev.kyrion.core.conversation.ConversationRepository
import dev.kyrion.core.conversation.ConversationNotFoundException
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
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.status
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer
import java.sql.Timestamp
import java.time.Instant
import java.util.UUID

@Testcontainers
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@AutoConfigureMockMvc
class AuthenticationPersistenceIntegrationTest @Autowired constructor(
    private val authentication: LocalAuthenticationService,
    private val conversations: ConversationRepository,
    private val passwordHashing: PasswordHashingService,
    private val jdbc: JdbcClient,
    private val mockMvc: MockMvc,
) {
    @BeforeEach
    fun cleanDatabase() {
        jdbc.sql(
            "TRUNCATE TABLE conversation_message, conversation, auth_session, user_account, activity_event CASCADE",
        ).update()
    }

    @Test
    fun `setup closes permanently and login persists across service calls`() {
        assertThat(authentication.setupRequired()).isTrue()
        val owner = authentication.setup(" Flo ", OLD_PASSWORD)

        assertThat(authentication.setupRequired()).isFalse()
        assertThat(authentication.authenticate(owner.session.rawToken)?.username).isEqualTo("flo")
        assertThat(authentication.login("FLO", OLD_PASSWORD).user.id).isEqualTo(owner.user.id)
        assertThatThrownBy { authentication.setup("other", OTHER_PASSWORD) }
            .isInstanceOf(SetupAlreadyCompletedException::class.java)
    }

    @Test
    fun `password change revokes every existing session and persists only the new password`() {
        val owner = authentication.setup("flo", OLD_PASSWORD)
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
        val first = authentication.setup("first", OLD_PASSWORD).user
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
            post("/v1/auth/setup").contentType(MediaType.APPLICATION_JSON)
                .content("""{"username":"flo","password":"$OLD_PASSWORD"}"""),
        ).andExpect(status().isCreated)
            .andExpect(jsonPath("$.user.username").value("flo"))
            .andExpect(jsonPath("$.sessionToken").isString)
            .andReturn()
        val token = Regex("\"sessionToken\":\"([^\"]+)\"").find(setupResult.response.contentAsString)!!.groupValues[1]

        mockMvc.perform(
            post("/v1/auth/setup").contentType(MediaType.APPLICATION_JSON)
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
        private const val OLD_PASSWORD = "old-secure-password"
        private const val NEW_PASSWORD = "new-secure-password"
        private const val OTHER_PASSWORD = "other-secure-password"

        @Container
        @JvmStatic
        val postgres = PostgreSQLContainer("postgres:17-alpine")

        @DynamicPropertySource
        @JvmStatic
        fun databaseProperties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url", postgres::getJdbcUrl)
            registry.add("spring.datasource.username", postgres::getUsername)
            registry.add("spring.datasource.password", postgres::getPassword)
        }
    }
}
