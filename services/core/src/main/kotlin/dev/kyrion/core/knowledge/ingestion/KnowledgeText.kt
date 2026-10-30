package dev.kyrion.core.knowledge.ingestion

import dev.kyrion.core.knowledge.domain.*
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.io.DataInputStream
import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.nio.file.*
import java.text.Normalizer
import java.util.concurrent.TimeUnit

@Component
class KnowledgeText(@Value("\${kyrion.knowledge.parser-jar:build/libs/knowledge-parser.jar}") private val parserJar: String) {
    fun extract(path: Path, mediaType: String): List<Pair<Int?, String>> {
        val pages = if (mediaType == "text/plain") {
            try {
                val decoded = Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                    .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(Files.readAllBytes(path)))
                    .toString()
                if (decoded.any { it == '\u0000' || (it.code < 32 && it !in "\n\r\t") }) throw KnowledgeFailure("KNOWLEDGE_INVALID_TEXT")
                listOf(null to decoded)
            } catch (e: KnowledgeFailure) {
                throw e
            } catch (_: Exception) {
                throw KnowledgeFailure("KNOWLEDGE_INVALID_TEXT")
            }
        } else parsePdf(path)
        val normalized = pages.map { (page, text) ->
            page to Normalizer.normalize(text, Normalizer.Form.NFC)
                .replace("\r\n", "\n").replace('\r', '\n').replace(Regex("[\\t ]+"), " ").trim()
        }
        if (normalized.all { it.second.isBlank() }) throw KnowledgeFailure("KNOWLEDGE_NO_TEXT")
        if (normalized.sumOf { it.second.length } > 1_000_000) throw KnowledgeFailure("KNOWLEDGE_TEXT_LIMIT")
        return normalized
    }

    private fun parsePdf(path: Path): List<Pair<Int?, String>> {
        val header = Files.newInputStream(path).use { it.readNBytes(5) }
        if (!header.contentEquals("%PDF-".toByteArray())) throw KnowledgeFailure("KNOWLEDGE_INVALID_PDF")
        if (!Files.isRegularFile(Path.of(parserJar))) throw KnowledgeFailure("KNOWLEDGE_PARSER_UNAVAILABLE", 503)
        val output = Files.createTempFile("knowledge-parser-", ".bin")
        try {
            val executable = Path.of(
                System.getProperty("java.home"),
                "bin",
                if (System.getProperty("os.name").startsWith("Windows")) "java.exe" else "java"
            ).toString()
            val process = ProcessBuilder(
                executable, "-Xmx128m", "-XX:MaxMetaspaceSize=64m", "-cp", parserJar,
                "dev.kyrion.core.knowledge.ingestion.PdfParserMain", path.toString()
            )
                .redirectOutput(output.toFile()).redirectError(ProcessBuilder.Redirect.DISCARD).start()
            try {
                if (!process.waitFor(20, TimeUnit.SECONDS)) throw KnowledgeFailure("KNOWLEDGE_PDF_LIMIT")
                when (process.exitValue()) {
                    0 -> Unit
                    21 -> throw KnowledgeFailure("KNOWLEDGE_ENCRYPTED_PDF")
                    22 -> throw KnowledgeFailure("KNOWLEDGE_PDF_LIMIT")
                    else -> throw KnowledgeFailure("KNOWLEDGE_INVALID_PDF")
                }
            } finally {
                if (process.isAlive) {
                    process.destroyForcibly(); process.waitFor(5, TimeUnit.SECONDS)
                }
            }
            if (Files.size(output) > 4_001_000) throw KnowledgeFailure("KNOWLEDGE_PDF_LIMIT")
            DataInputStream(Files.newInputStream(output)).use { input ->
                val count = input.readInt()
                if (count !in 0..200) throw KnowledgeFailure("KNOWLEDGE_INVALID_PDF")
                return (1..count).map { page ->
                    val length = input.readInt()
                    if (length !in 0..4_000_000) throw KnowledgeFailure("KNOWLEDGE_PDF_LIMIT")
                    page to String(input.readNBytes(length), Charsets.UTF_8)
                }
            }
        } finally {
            Files.deleteIfExists(output)
        }
    }
}

/** Offsets refer to normalized page text; 2,000 characters (~500 tokens), 200 overlap. */
fun knowledgeChunks(pages: List<Pair<Int?, String>>): List<KnowledgeChunk> {
    val result = mutableListOf<KnowledgeChunk>()
    pages.forEach { (page, text) ->
        var start = 0
        while (start < text.length) {
            val end = minOf(start + 2000, text.length)
            val content = text.substring(start, end)
            if (content.isNotBlank()) result.add(KnowledgeChunk(result.size, content, page, start, end))
            if (end == text.length) break
            start = end - 200
        }
    }
    if (result.size > 600) throw KnowledgeFailure("KNOWLEDGE_TEXT_LIMIT")
    return result
}
