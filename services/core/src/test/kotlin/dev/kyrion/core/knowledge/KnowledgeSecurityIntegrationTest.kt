package dev.kyrion.core.knowledge

import dev.kyrion.core.ai.*
import dev.kyrion.core.knowledge.application.KnowledgeService
import dev.kyrion.core.knowledge.domain.*
import dev.kyrion.core.knowledge.ingestion.*
import dev.kyrion.core.knowledge.persistence.*
import dev.kyrion.core.security.*
import org.assertj.core.api.Assertions.*
import org.junit.jupiter.api.*
import org.mockito.Mockito.`when`
import org.springframework.beans.factory.annotation.Autowired
import org.springframework.boot.test.context.SpringBootTest
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.mock.web.MockMultipartFile
import org.springframework.test.context.*
import org.springframework.test.context.bean.override.mockito.MockitoBean
import org.springframework.test.web.servlet.MockMvc
import org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*
import org.springframework.test.web.servlet.result.MockMvcResultMatchers.*
import org.testcontainers.junit.jupiter.*
import org.testcontainers.postgresql.PostgreSQLContainer
import java.nio.file.Files
import java.util.UUID

@Testcontainers
@SpringBootTest
@AutoConfigureMockMvc
@org.springframework.context.annotation.Import(AiTestGatewayConfiguration::class)
class KnowledgeSecurityIntegrationTest @Autowired constructor(
    private val jdbc: JdbcClient, private val auth: LocalAuthenticationService,
    private val hashing: PasswordHashingService, private val rbac: RbacService,
    private val service: KnowledgeService, private val repository: KnowledgeRepository,
    private val worker: KnowledgeWorker, private val mvc: MockMvc,
    private val ai: AiOrchestrationService, private val aiGateway: AiTestGateway,
) {
    @MockitoBean
    lateinit var embeddings: EmbeddingProvider
    private lateinit var a: AuthenticatedOwner
    private lateinit var b: AuthenticatedOwner
    private lateinit var space: KnowledgeSpace

    @BeforeEach
    fun setup() {
        jdbc.sql("TRUNCATE user_account,activity_event,activity_integrity_chain CASCADE").update()
        jdbc.sql("UPDATE installation_bootstrap_state SET initialized=FALSE").update()
        a = auth.setup("knowledge-a", "secure-knowledge-password", secret)
        val user = UUID.randomUUID()
        jdbc.sql("INSERT INTO user_account(id,username,password_hash,workspace_owner_id) VALUES(:id,'knowledge-b',:hash,:owner)")
            .param("id", user).param("hash", hashing.hash("secure-knowledge-password")).param("owner", a.user.id)
            .update()
        rbac.initializeUser(user, a.user.id, false)
        b = auth.login("knowledge-b", "secure-knowledge-password")
        space = service.createSpace(a.user.id)
        `when`(embeddings.modelId).thenReturn("test-local-embedding")
        `when`(embeddings.dimension).thenReturn(3)
        `when`(embeddings.embed(org.mockito.ArgumentMatchers.anyList())).thenAnswer { invocation ->
            val texts = invocation.getArgument<List<String>>(0)
            texts.map { listOf(1f, 0f, 0f) }
        }
        aiGateway.reset()
    }

    private fun upload(text: String = "The private launch code is apricot. Budget is 42 francs."): KnowledgeDocument =
        service.upload(a.user.id, space.id, "private.txt", "text/plain", text.byteInputStream())

    private fun search(actor: UUID) =
        service.search(actor, service.spaces(actor).map { it.id }, "What is the budget?", 3)

    @Test
    fun `personal knowledge remains private across canonical Spaces and multi Space startup stays blocked`() {
        val document = upload()
        worker.runOnce()
        val foreign = UUID.randomUUID()
        jdbc.sql("INSERT INTO user_account(id,username,password_hash) VALUES(:id,'foreign-space-owner',:hash)")
            .param("id", foreign).param("hash", hashing.hash("foreign-space-password")).update()
        rbac.initializeUser(foreign, foreign, true)
        val token = auth.login("foreign-space-owner", "foreign-space-password").session.rawToken
        val foreignSpace = service.createSpace(foreign)
        assertThat(service.documents(foreign, foreignSpace.id, 50, 0)).isEmpty()
        org.mockito.Mockito.clearInvocations(embeddings)
        listOf("/v1/knowledge/documents/${document.id}", "/v1/knowledge/documents/${document.id}/content",
            "/v1/knowledge/spaces/${space.id}/documents").forEach { path ->
            mvc.perform(get(path).header("Authorization", "Bearer $token")).andExpect(status().isNotFound)
        }
        mvc.perform(delete("/v1/knowledge/documents/${document.id}").header("Authorization", "Bearer $token"))
            .andExpect(status().isNotFound)
        mvc.perform(post("/v1/knowledge/documents/${document.id}/reindex").header("Authorization", "Bearer $token"))
            .andExpect(status().isNotFound)
        assertThatThrownBy { service.search(foreign, listOf(space.id), "private budget", 3) }
            .isInstanceOf(KnowledgeFailure::class.java)
        org.mockito.Mockito.verify(embeddings, org.mockito.Mockito.never()).embed(org.mockito.ArgumentMatchers.anyList())
        assertThatThrownBy { SingleSpaceRuntimeGuard(jdbc).run(org.springframework.boot.DefaultApplicationArguments()) }
            .isInstanceOf(IllegalStateException::class.java).hasMessageContaining("MULTI_SPACE_RUNTIME_UNSUPPORTED")
    }

    @Test
    fun `suspended canonical Space denies personal APIs and ingestion before embedding`() {
        upload()
        jdbc.sql("UPDATE kyrion_space SET status='SUSPENDED' WHERE id=:id").param("id", a.user.id).update()
        org.mockito.Mockito.clearInvocations(embeddings)
        assertThatThrownBy { service.spaces(a.user.id) }.isInstanceOf(ForbiddenException::class.java)
        assertThat(repository.claim()).isNull()
        worker.runOnce()
        org.mockito.Mockito.verify(embeddings, org.mockito.Mockito.never()).embed(org.mockito.ArgumentMatchers.anyList())
        assertThat(jdbc.sql("SELECT count(*) FROM knowledge_chunks").query(Long::class.java).single()).isZero()
    }

    @Test
    fun `Space suspension during embedding fences publication`() {
        upload()
        org.mockito.Mockito.doAnswer { invocation ->
            jdbc.sql("UPDATE kyrion_space SET status='SUSPENDED' WHERE id=:id").param("id", a.user.id).update()
            invocation.getArgument<List<String>>(0).map { listOf(1f, 0f, 0f) }
        }.`when`(embeddings).embed(org.mockito.ArgumentMatchers.anyList())
        worker.runOnce()
        assertThat(jdbc.sql("SELECT count(*) FROM knowledge_chunks").query(Long::class.java).single()).isZero()
        assertThat(jdbc.sql("SELECT count(*) FROM knowledge_documents WHERE status='READY'").query(Long::class.java).single()).isZero()
    }

    @Test
    fun `upload download search and foreign UUID access enforce actor privacy including admins`() {
        val file = MockMultipartFile("file", "private.txt", "text/plain", "Private budget 42 francs".toByteArray())
        val uploaded = mvc.perform(
            multipart("/v1/knowledge/spaces/${space.id}/documents").file(file)
                .header("Authorization", "Bearer ${a.session.rawToken}")
        )
            .andExpect(status().isOk).andExpect(jsonPath("$.status").value("PENDING"))
            .andExpect(jsonPath("$.storageKey").doesNotExist()).andReturn()
        val id = aiJson.readTree(uploaded.response.contentAsString).path("id").asText()
        worker.runOnce()
        mvc.perform(get("/v1/knowledge/documents/$id").header("Authorization", "Bearer ${a.session.rawToken}"))
            .andExpect(status().isOk).andExpect(jsonPath("$.status").value("READY"))
        mvc.perform(get("/v1/knowledge/documents/$id/content").header("Authorization", "Bearer ${a.session.rawToken}"))
            .andExpect(status().isOk).andExpect(content().string("Private budget 42 francs"))
        service.createSpace(b.user.id)
        assertThat(search(b.user.id)).isEmpty()
        assertThat(search(a.user.id).single().documentId.toString()).isEqualTo(id)
        for (admin in listOf(false, true)) {
            if (admin) jdbc.sql("INSERT INTO rbac_user_role(user_id,role_id) SELECT :user,id FROM rbac_role WHERE installation_owner_id=:owner AND role_key='ADMIN' ON CONFLICT DO NOTHING")
                .param("user", b.user.id).param("owner", a.user.id).update()
            for (path in listOf(
                "/v1/knowledge/spaces/${space.id}/documents",
                "/v1/knowledge/documents/$id",
                "/v1/knowledge/documents/$id/content"
            ))
                mvc.perform(get(path).header("Authorization", "Bearer ${b.session.rawToken}"))
                    .andExpect(status().isNotFound)
            mvc.perform(delete("/v1/knowledge/documents/$id").header("Authorization", "Bearer ${b.session.rawToken}"))
                .andExpect(status().isNotFound)
            assertThat(search(b.user.id)).isEmpty()
        }
    }

    @Test
    fun `pending failed and deleted documents never appear and cleanup is recoverable`() {
        val document = upload()
        assertThat(search(a.user.id)).isEmpty()
        `when`(embeddings.embed(org.mockito.ArgumentMatchers.anyList())).thenThrow(
            KnowledgeFailure(
                "KNOWLEDGE_EMBEDDING_SETUP_REQUIRED",
                503
            )
        )
        worker.runOnce()
        assertThat(service.document(a.user.id, document.id).status).isEqualTo("FAILED")
        assertThat(service.document(a.user.id, document.id).errorCode).isEqualTo("KNOWLEDGE_EMBEDDING_SETUP_REQUIRED")
        assertThat(jdbc.sql("SELECT count(*) FROM knowledge_chunks").query(Long::class.java).single()).isZero()
        org.mockito.Mockito.reset(embeddings)
        `when`(embeddings.modelId).thenReturn("test-local-embedding")
        `when`(embeddings.dimension).thenReturn(3)
        `when`(embeddings.embed(org.mockito.ArgumentMatchers.anyList())).thenAnswer { invocation ->
            invocation.getArgument<List<String>>(
                0
            ).map { listOf(1f, 0f, 0f) }
        }
        service.reindex(a.user.id, document.id); worker.runOnce()
        assertThat(search(a.user.id)).hasSize(1)
        service.delete(a.user.id, document.id)
        assertThat(search(a.user.id)).isEmpty()
        worker.cleanup()
        assertThat(jdbc.sql("SELECT count(*) FROM knowledge_documents").query(Long::class.java).single()).isZero()
        assertThat(jdbc.sql("SELECT count(*) FROM knowledge_chunks").query(Long::class.java).single()).isZero()
    }

    @Test
    fun `expired workers are fenced and deletion during indexing cannot resurrect content`() {
        val document = upload()
        val old = repository.claim()!!
        jdbc.sql("UPDATE knowledge_ingestion_jobs SET lease_expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second'").update()
        val recovered = repository.claim()!!
        val chunks = knowledgeChunks(listOf(null to "Recovered text"))
        assertThat(repository.publish(old, chunks, listOf(listOf(1f, 0f, 0f)), "test-local-embedding", 3)).isFalse()
        service.delete(a.user.id, document.id)
        assertThat(
            repository.publish(
                recovered,
                chunks,
                listOf(listOf(1f, 0f, 0f)),
                "test-local-embedding",
                3
            )
        ).isFalse()
        assertThat(search(a.user.id)).isEmpty()
    }

    @Test
    fun `reindex never mixes models dimensions or revisions`() {
        val document = upload(); worker.runOnce()
        val source = search(a.user.id).single()
        assertThat(source.reference).isEqualTo("kd:${document.id}:1:0")
        assertThat(source.filename).isEqualTo("private.txt")
        `when`(embeddings.dimension).thenReturn(2)
        `when`(embeddings.embed(org.mockito.ArgumentMatchers.anyList())).thenAnswer { invocation ->
            invocation.getArgument<List<String>>(
                0
            ).map { listOf(1f, 0f) }
        }
        assertThat(search(a.user.id)).isEmpty()
        service.reindex(a.user.id, document.id)
        assertThat(search(a.user.id)).isEmpty()
        worker.runOnce()
        assertThat(search(a.user.id).single().reference).isEqualTo("kd:${document.id}:2:0")
        assertThat(
            jdbc.sql("SELECT DISTINCT embedding_dimension FROM knowledge_chunks").query(Int::class.java).list()
        ).containsExactly(2)
    }

    @Test
    fun `malformed pdf traversal oversized and invalid utf8 fail without accepted documents`() {
        fun rejected(name: String, type: String, bytes: ByteArray, code: String) {
            assertThatThrownBy { service.upload(a.user.id, space.id, name, type, bytes.inputStream()) }
                .isInstanceOf(KnowledgeFailure::class.java).hasMessage(code)
        }
        rejected("../secret.txt", "text/plain", "abc".toByteArray(), "KNOWLEDGE_INVALID_FILENAME")
        rejected("broken.pdf", "application/pdf", "%PDF-1.7\nbroken".toByteArray(), "KNOWLEDGE_INVALID_PDF")
        rejected("large.txt", "text/plain", ByteArray(1025) { 65 }, "KNOWLEDGE_TOO_LARGE")
        rejected("bad.txt", "text/plain", byteArrayOf(0xc3.toByte(), 0x28), "KNOWLEDGE_INVALID_TEXT")
        assertThat(jdbc.sql("SELECT count(*) FROM knowledge_documents").query(Long::class.java).single()).isZero()
    }

    @Test
    fun `knowledge uses existing local streaming and persists correct answer references`() {
        val document = upload(); worker.runOnce()
        val conversation = UUID.randomUUID();
        val turn = UUID.randomUUID()
        mvc.perform(
            post("/v1/conversations/$conversation/turns").header("Authorization", "Bearer ${a.session.rawToken}")
                .contentType("application/json")
                .content("""{"title":"Knowledge","message":{"id":"$turn","role":"user","content":"What is the budget?","createdAt":"2026-10-30T12:00:00Z"}}""")
        )
            .andExpect(status().isOk)
        val prepared = ai.prepare(a.user.id, AiGenerationRequest(conversation, turn, knowledgeEnabled = true))
        assertThat(prepared.knowledgeSources.single().documentId).isEqualTo(document.id)
        val frames = mutableListOf<String>(); ai.stream(prepared, frames::add)
        assertThat(frames.any { it.contains("knowledge.sources") && it.contains(document.id.toString()) }).isTrue()
        assertThat(frames.any { it.contains("message.completed") }).isTrue()
        assertThat(
            jdbc.sql("SELECT document_id FROM knowledge_answer_sources").query(UUID::class.java).single()
        ).isEqualTo(document.id)
        mvc.perform(get("/v1/knowledge/answers/$conversation").header("Authorization", "Bearer ${b.session.rawToken}"))
            .andExpect(status().isOk).andExpect(content().json("[]"))
    }

    @Test fun `competing workers only claim one revision and exhausted crash leases fail explicitly`() {
        val document = upload()
        val executor = java.util.concurrent.Executors.newFixedThreadPool(2)
        try {
            val futures = (1..2).map { executor.submit<KnowledgeJob?> { repository.claim() } }
            val claims = futures.mapNotNull { it.get(10, java.util.concurrent.TimeUnit.SECONDS) }
            assertThat(claims).hasSize(1)
            jdbc.sql("UPDATE knowledge_ingestion_jobs SET attempt_count=3,lease_expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second'").update()
            assertThat(repository.claim()).isNull()
            assertThat(service.document(a.user.id, document.id).status).isEqualTo("FAILED")
            assertThat(service.document(a.user.id, document.id).errorCode).isEqualTo("KNOWLEDGE_RETRY_EXHAUSTED")
        } finally { executor.shutdownNow() }
    }
    @Test fun `delete during embedding cannot publish content`() {
        val document = upload("a".repeat(500))
        org.mockito.Mockito.doAnswer { invocation ->
            service.delete(a.user.id, document.id)
            invocation.getArgument<List<String>>(0).map { listOf(1f,0f,0f) }
        }.`when`(embeddings).embed(org.mockito.ArgumentMatchers.anyList())
        worker.runOnce()
        assertThat(jdbc.sql("SELECT count(*) FROM knowledge_chunks").query(Long::class.java).single()).isZero()
        assertThat(repository.search(a.user.id, listOf(space.id), listOf(1f,0f,0f), "test-local-embedding", 3, 3)).isEmpty()
    }

    companion object {
        private val secret = SessionTokenService().create().rawToken
        private val temp = Files.createTempDirectory("knowledge-tests")
        private val bootstrap = temp.resolve("bootstrap").also { Files.writeString(it, secret) }
        private val key = temp.resolve("key").also { Files.write(it, ByteArray(32) { (it + 1).toByte() }) }
        @Container
        @JvmStatic
        val postgres = PostgreSQLContainer("postgres:17-alpine").withStartupTimeout(java.time.Duration.ofMinutes(3))
        @DynamicPropertySource
        @JvmStatic
        fun properties(registry: DynamicPropertyRegistry) {
            registry.add("spring.datasource.url", postgres::getJdbcUrl)
            registry.add("spring.datasource.username", postgres::getUsername)
            registry.add("spring.datasource.password", postgres::getPassword)
            registry.add("kyrion.security.bootstrap-secret-file") { bootstrap.toString() }
            registry.add("kyrion.audit.integrity-key-file") { key.toString() }
            registry.add("kyrion.credentials.key-file") { key.toString() }
            registry.add("kyrion.knowledge.root") { temp.resolve("documents").toString() }
            registry.add("kyrion.knowledge.max-bytes") { "1024" }
            registry.add("kyrion.knowledge.worker-enabled") { "false" }
            registry.add("kyrion.calendar.sync.scheduler-enabled") { "false" }
            registry.add("kyrion.home-assistant.refresh-enabled") { "false" }
        }
    }
}
