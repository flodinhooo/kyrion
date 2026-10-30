package dev.kyrion.core.knowledge

import dev.kyrion.core.knowledge.domain.KnowledgeFailure
import dev.kyrion.core.knowledge.ingestion.*
import dev.kyrion.core.knowledge.storage.LocalKnowledgeObjectStore
import org.apache.pdfbox.pdmodel.*
import org.apache.pdfbox.pdmodel.font.PDType1Font
import org.apache.pdfbox.pdmodel.font.Standard14Fonts
import org.apache.pdfbox.pdmodel.encryption.*
import org.assertj.core.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import com.sun.net.httpserver.HttpServer
import java.net.InetSocketAddress
import java.nio.file.*
import java.util.concurrent.atomic.AtomicInteger

class KnowledgeLocalComponentsTest {
    @TempDir lateinit var temp: Path
    @Test fun `valid pdf extracts actual pages and encrypted scanned malformed pdfs fail safely`() {
        val extractor = KnowledgeText("build/libs/knowledge-parser.jar")
        val valid = temp.resolve("valid.pdf")
        PDDocument().use { pdf ->
            val page = PDPage(); pdf.addPage(page)
            PDPageContentStream(pdf, page).use { stream ->
                stream.beginText(); stream.setFont(PDType1Font(Standard14Fonts.FontName.HELVETICA), 12f)
                stream.newLineAtOffset(50f, 700f); stream.showText("The budget is forty two francs."); stream.endText()
            }
            pdf.save(valid.toFile())
        }
        assertThat(extractor.extract(valid, "application/pdf").single()).isEqualTo(1 to "The budget is forty two francs.")
        val encrypted = temp.resolve("encrypted.pdf")
        PDDocument().use { pdf ->
            pdf.addPage(PDPage()); pdf.protect(StandardProtectionPolicy("owner", "private", AccessPermission()))
            pdf.save(encrypted.toFile())
        }
        assertThatThrownBy { extractor.extract(encrypted, "application/pdf") }.hasMessage("KNOWLEDGE_ENCRYPTED_PDF")
        val empty = temp.resolve("scanned.pdf")
        PDDocument().use { pdf -> pdf.addPage(PDPage()); pdf.save(empty.toFile()) }
        assertThatThrownBy { extractor.extract(empty, "application/pdf") }.hasMessage("KNOWLEDGE_NO_TEXT")
        val malformed = temp.resolve("broken.pdf").also { Files.writeString(it, "%PDF-broken") }
        assertThatThrownBy { extractor.extract(malformed, "application/pdf") }.hasMessage("KNOWLEDGE_INVALID_PDF")
        // A second parse verifies that parser failures release the bounded permit.
        assertThat(extractor.extract(valid, "application/pdf")).hasSize(1)
    }
    @Test fun `chunks preserve page offsets order and bounded overlap`() {
        val text = "abcdefghij".repeat(500)
        val chunks = knowledgeChunks(listOf(2 to text))
        assertThat(chunks.map { it.index }).containsExactly(0,1,2)
        chunks.forEach { assertThat(it.content).isEqualTo(text.substring(it.start, it.end)); assertThat(it.page).isEqualTo(2) }
        assertThat(chunks[0].end - chunks[1].start).isEqualTo(200)
        assertThat(chunks.last().end).isEqualTo(text.length)
    }
    @Test fun `atomic storage bounds bytes randomizes keys and sweeps only old orphans`() {
        val store = LocalKnowledgeObjectStore(temp.toString(), 10)
        val first = store.store("private".byteInputStream()).first
        val second = store.store("private".byteInputStream()).first
        assertThat(first).isNotEqualTo(second)
        assertThat(store.path(first).parent).isEqualTo(temp)
        assertThatThrownBy { store.store("far too much content".byteInputStream()) }.hasMessage("KNOWLEDGE_TOO_LARGE")
        Files.setLastModifiedTime(store.path(first), java.nio.file.attribute.FileTime.fromMillis(1))
        Files.setLastModifiedTime(store.path(second), java.nio.file.attribute.FileTime.fromMillis(1))
        store.sweep(setOf(first))
        assertThat(Files.exists(store.path(first))).isTrue()
        assertThat(Files.exists(store.path(second))).isFalse()
        Files.newDirectoryStream(temp).use { assertThat(it.toList()).hasSize(1) }
    }
    @Test fun `embedding capability requires explicit local setup and never falls back to cloud`() {
        assertThatThrownBy { LocalEmbeddings("http://127.0.0.1:11434", "", 3).embed(listOf("text")) }
            .isInstanceOf(KnowledgeFailure::class.java).hasMessage("KNOWLEDGE_EMBEDDING_SETUP_REQUIRED")
        assertThatThrownBy { LocalEmbeddings("https://api.openai.com", "test", 3).embed(listOf("text")) }
            .hasMessage("KNOWLEDGE_LOCAL_RUNTIME_REQUIRED")
        val requests = AtomicInteger()
        val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        var body = "{\"error\":\"model missing\"}"
        var status = 404
        server.createContext("/api/embed") { exchange ->
            requests.incrementAndGet()
            val request = String(exchange.requestBody.readAllBytes())
            assertThat(request).contains("\"model\":\"test-embedding\"", "\"truncate\":false")
            val bytes = body.toByteArray(); exchange.sendResponseHeaders(status, bytes.size.toLong())
            exchange.responseBody.use { it.write(bytes) }
        }
        server.start()
        try {
            val client = LocalEmbeddings("http://127.0.0.1:${server.address.port}", "test-embedding", 3)
            assertThatThrownBy { client.embed(listOf("hello")) }.hasMessage("KNOWLEDGE_EMBEDDING_UNAVAILABLE")
            assertThat(requests.get()).isEqualTo(1)
            body = "{\"embeddings\":[[1,0]]}"; status = 200
            assertThatThrownBy { client.embed(listOf("hello")) }.hasMessage("KNOWLEDGE_DIMENSION_MISMATCH")
            body = "{\"embeddings\":[[1,0,0]]}"
            assertThat(client.embed(listOf("hello"))).containsExactly(listOf(1f,0f,0f))
        } finally { server.stop(0) }
    }
}
