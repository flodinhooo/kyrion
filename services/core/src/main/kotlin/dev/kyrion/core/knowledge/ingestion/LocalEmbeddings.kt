package dev.kyrion.core.knowledge.ingestion

import dev.kyrion.core.ai.aiJson
import dev.kyrion.core.knowledge.domain.KnowledgeFailure
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.net.URI
import java.net.InetAddress
import java.net.http.*
import java.time.Duration
import java.util.concurrent.Semaphore

interface EmbeddingProvider {
    val modelId: String
    val dimension: Int
    fun embed(texts: List<String>): List<List<Float>>
}

/** Separate embedding capability; no chat router, cloud credentials or fallback. */
@Component
class LocalEmbeddings(
    @Value("\${kyrion.knowledge.embedding-url:http://127.0.0.1:11434}") private val url: String,
    @Value("\${kyrion.knowledge.embedding-model:}") override val modelId: String,
    @Value("\${kyrion.knowledge.embedding-dimension:768}") override val dimension: Int,
) : EmbeddingProvider {
    private val client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3))
        .followRedirects(HttpClient.Redirect.NEVER).build()
    private val permit = Semaphore(1)

    init {
        require(dimension in 1..4096); require(modelId.length <= 128)
    }

    override fun embed(texts: List<String>): List<List<Float>> {
        if (modelId.isBlank()) throw KnowledgeFailure("KNOWLEDGE_EMBEDDING_SETUP_REQUIRED", 503)
        if (texts.isEmpty() || texts.size > 8 || texts.any { it.length !in 1..8000 }) throw KnowledgeFailure("INVALID_REQUEST")
        if (!permit.tryAcquire()) throw KnowledgeFailure("KNOWLEDGE_EMBEDDING_BUSY", 503)
        try {
            val uri = URI(url)
            if (uri.scheme != "http" || uri.userInfo != null || uri.rawQuery != null || uri.rawFragment != null || uri.path !in listOf(
                    "",
                    "/"
                )
            )
                throw KnowledgeFailure("KNOWLEDGE_LOCAL_RUNTIME_REQUIRED", 503)
            val addresses = InetAddress.getAllByName(uri.host)
            if (addresses.isEmpty() || addresses.any { !it.isLoopbackAddress && !it.isSiteLocalAddress })
                throw KnowledgeFailure("KNOWLEDGE_LOCAL_RUNTIME_REQUIRED", 503)
            val request = HttpRequest.newBuilder(URI(url.trimEnd('/') + "/api/embed"))
                .timeout(Duration.ofSeconds(30)).header("Content-Type", "application/json")
                .POST(
                    HttpRequest.BodyPublishers.ofString(
                        aiJson.writeValueAsString(
                            mapOf(
                                "model" to modelId, "input" to texts, "truncate" to false
                            )
                        )
                    )
                ).build()
            val response = client.send(request, HttpResponse.BodyHandlers.ofInputStream())
            response.body().use { input ->
                val deadline =
                    deadlines.schedule({ runCatching { input.close() } }, 30, java.util.concurrent.TimeUnit.SECONDS)
                try {
                val bytes = input.readNBytes(1_000_001)
                if (response.statusCode() != 200 || bytes.size > 1_000_000) throw KnowledgeFailure(
                    "KNOWLEDGE_EMBEDDING_UNAVAILABLE",
                    503
                )
                val vectors = aiJson.readTree(bytes).path("embeddings")
                if (!vectors.isArray || vectors.size() != texts.size) throw KnowledgeFailure(
                    "KNOWLEDGE_EMBEDDING_INVALID",
                    503
                )
                return vectors.map { vector ->
                    if (!vector.isArray || vector.size() != dimension) throw KnowledgeFailure(
                        "KNOWLEDGE_DIMENSION_MISMATCH",
                        503
                    )
                    vector.map { value ->
                        if (!value.isNumber || !value.floatValue()
                                .isFinite()
                        ) throw KnowledgeFailure("KNOWLEDGE_EMBEDDING_INVALID", 503)
                        value.floatValue()
                    }.also { if (it.all { n -> n == 0f }) throw KnowledgeFailure("KNOWLEDGE_EMBEDDING_INVALID", 503) }
                }
                } finally {
                    deadline.cancel(false)
                }
            }
        } catch (failure: KnowledgeFailure) {
            throw failure
        } catch (_: Exception) {
            throw KnowledgeFailure("KNOWLEDGE_EMBEDDING_UNAVAILABLE", 503)
        } finally {
            permit.release()
        }
    }

    companion object {
        private val deadlines = java.util.concurrent.Executors.newSingleThreadScheduledExecutor { task ->
            Thread(task, "knowledge-embedding-deadline").apply { isDaemon = true }
        }
    }
}
