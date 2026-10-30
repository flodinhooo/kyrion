package dev.kyrion.core.knowledge.storage

import dev.kyrion.core.knowledge.domain.KnowledgeFailure
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.io.InputStream
import java.nio.file.*
import java.time.Instant
import java.util.UUID

interface KnowledgeObjectStore {
    fun store(input: InputStream): Pair<UUID, Long>
    fun path(key: UUID): Path
    fun delete(key: UUID)
}

@Component
class LocalKnowledgeObjectStore(
    @Value("\${kyrion.knowledge.root:./data/knowledge}") directory: String,
    @Value("\${kyrion.knowledge.max-bytes:10485760}") val maxBytes: Long = 10485760,
) : KnowledgeObjectStore {
    val root: Path = Paths.get(directory).toAbsolutePath().normalize()

    init {
        require(maxBytes in 1..50_000_000); Files.createDirectories(root); require(!Files.isSymbolicLink(root))
    }

    override fun path(key: UUID): Path = root.resolve(key.toString()).also {
        if (it.parent != root || Files.isSymbolicLink(it)) throw KnowledgeFailure("KNOWLEDGE_STORAGE_INVALID", 503)
    }

    override fun store(input: InputStream): Pair<UUID, Long> {
        val key = UUID.randomUUID()
        val temp = Files.createTempFile(root, ".upload-", ".tmp")
        try {
            var size = 0L
            java.nio.channels.FileChannel.open(temp, StandardOpenOption.WRITE).use { channel ->
                val bytes = ByteArray(8192)
                while (true) {
                    val count = input.read(bytes)
                    if (count < 0) break
                    size += count
                    if (size > maxBytes) throw KnowledgeFailure("KNOWLEDGE_TOO_LARGE", 413)
                    val buffer = java.nio.ByteBuffer.wrap(bytes, 0, count)
                    while (buffer.hasRemaining()) channel.write(buffer)
                }
                channel.force(true)
            }
            if (size == 0L) throw KnowledgeFailure("KNOWLEDGE_EMPTY")
            Files.move(temp, path(key), StandardCopyOption.ATOMIC_MOVE)
            return key to size
        } finally {
            Files.deleteIfExists(temp)
        }
    }

    override fun delete(key: UUID) {
        Files.deleteIfExists(path(key))
    }

    fun sweep(referenced: Set<UUID>) {
        val cutoff = Instant.now().minusSeconds(86400)
        Files.newDirectoryStream(root).use { paths ->
            paths.forEach { candidate ->
                if (!Files.isSymbolicLink(candidate) && Files.isRegularFile(candidate) &&
                    Files.getLastModifiedTime(candidate).toInstant().isBefore(cutoff)
                ) {
                    val key = runCatching { UUID.fromString(candidate.fileName.toString()) }.getOrNull()
                    if ((key != null && key !in referenced) || candidate.fileName.toString().startsWith(".upload-"))
                        Files.deleteIfExists(candidate)
                }
            }
        }
    }
}
