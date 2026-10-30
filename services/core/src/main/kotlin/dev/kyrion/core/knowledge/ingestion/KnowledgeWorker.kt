package dev.kyrion.core.knowledge.ingestion

import dev.kyrion.core.activity.*
import dev.kyrion.core.knowledge.domain.KnowledgeFailure
import dev.kyrion.core.knowledge.persistence.KnowledgeRepository
import dev.kyrion.core.knowledge.storage.LocalKnowledgeObjectStore
import org.springframework.beans.factory.annotation.Value
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Component
import java.util.concurrent.atomic.AtomicBoolean

@Component
class KnowledgeWorker(
    private val repository: KnowledgeRepository, private val store: LocalKnowledgeObjectStore,
    private val extractor: KnowledgeText, private val embeddings: EmbeddingProvider,
    private val activity: ActivityService,
    @Value("\${kyrion.knowledge.worker-enabled:true}") private val enabled: Boolean = true,
) {
    private val running = AtomicBoolean()

    @Scheduled(fixedDelayString = "\${kyrion.knowledge.worker-ms:5000}", initialDelay = 15000)
    fun tick() {
        if (!enabled || !running.compareAndSet(false, true)) return
        try {
            runOnce()
        } finally {
            running.set(false)
        }
    }

    fun runOnce() {
        cleanup()
        val job = repository.claim() ?: return
        if (!repository.markProcessing(job)) return
        try {
            val chunks = knowledgeChunks(extractor.extract(store.path(job.storageKey), job.mediaType))
            val vectors = mutableListOf<List<Float>>()
            chunks.chunked(8).forEach { batch ->
                if (!repository.renew(job)) return
                vectors.addAll(embeddings.embed(batch.map { it.content }))
            }
            val published = repository.publish(job, chunks, vectors, embeddings.modelId, embeddings.dimension)
            if (published) activity.record(
                ActivityCategory.INTEGRATION,
                "knowledge.indexed",
                ActivityStatus.SUCCEEDED,
                ActivityActorType.SYSTEM,
                "kyrion-core",
                "knowledge.indexed",
                correlationId = job.documentId,
                ownerId = job.owner
            )
        } catch (failure: Exception) {
            val code = (failure as? KnowledgeFailure)?.code ?: "KNOWLEDGE_INGESTION_FAILED"
            repository.fail(job, code)
            activity.record(
                ActivityCategory.INTEGRATION, "knowledge.ingestion.failed", ActivityStatus.FAILED,
                ActivityActorType.SYSTEM, "kyrion-core", code, correlationId = job.documentId, ownerId = job.owner
            )
        }
    }

    fun cleanup() {
        repository.deleting().forEach { (id, key) -> runCatching { store.delete(key); repository.remove(id) } }
    }

    @Scheduled(fixedDelay = 3600000, initialDelay = 60000)
    fun sweep() {
        if (enabled) store.sweep(repository.keys())
    }
}
