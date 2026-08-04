package dev.kyrion.core.security

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
) {
    @BeforeEach
    fun cleanDatabase() {
        jdbc.sql(
            "TRUNCATE TABLE personal_memory, owner_memory_settings, conversation_turn, conversation_context_summary, conversation_message, conversation, auth_session, user_account, activity_event CASCADE",
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

        mockMvc.perform(delete("/v1/memory/$memoryId").header("Authorization", "Bearer $token"))
            .andExpect(status().isNoContent)
        assertThat(memories.find(ownerId, memoryId)).isNull()
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
            post("/v1/auth/setup").contentType(MediaType.APPLICATION_JSON)
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
