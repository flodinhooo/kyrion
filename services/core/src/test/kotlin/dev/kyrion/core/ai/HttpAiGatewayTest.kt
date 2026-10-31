package dev.kyrion.core.ai

import com.sun.net.httpserver.HttpServer
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.Assertions.*
import java.net.InetSocketAddress
import java.util.concurrent.Executors

/** Synthetic loopback HTTP server; no external model or paid provider calls. */
class HttpAiGatewayTest {
    private fun server(action: (com.sun.net.httpserver.HttpExchange) -> Unit, run: (HttpAiGateway) -> Unit) {
        val executor = Executors.newCachedThreadPool { Thread(it, "synthetic-ai").apply { isDaemon = true } }
        val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
        server.executor = executor
        server.createContext("/v1/chat/stream") { exchange ->
            exchange.use { runCatching { action(it) } }
        }
        server.createContext("/v1/models") { exchange ->
            exchange.use { runCatching { action(it) } }
        }
        server.start()
        try {
            run(HttpAiGateway("http://127.0.0.1:${server.address.port}"))
        } finally {
            server.stop(0); executor.shutdownNow()
        }
    }

    @Test
    fun `catalog and generation use HTTP 1 without h2c upgrades and retain the JSON body`() {
        val upgrades = mutableListOf<String>()
        val bodies = mutableListOf<String>()
        val correlation = java.util.UUID.randomUUID()
        var receivedCorrelation: String? = null
        server({ exchange ->
            if (exchange.requestURI.path.endsWith("/stream")) receivedCorrelation = exchange.requestHeaders.getFirst("X-Kyrion-Correlation-Id")
            upgrades.add(exchange.requestHeaders.getFirst("Upgrade") ?: "")
            bodies.add(exchange.requestBody.readAllBytes().toString(Charsets.UTF_8))
            val body = if (exchange.requestURI.path.endsWith("/models"))
                """{"defaultModelId":"fixture","models":[{"id":"fixture","maxOutputTokens":16}]}"""
            else """{"type":"message.completed"}""" + "\n"
            val bytes = body.toByteArray()
            exchange.sendResponseHeaders(200, bytes.size.toLong())
            exchange.responseBody.write(bytes)
        }) { gateway ->
            assertEquals("fixture", gateway.catalog().defaultModelId)
            gateway.streamTraced("{}", 3, correlation) {}
            assertEquals(correlation.toString(), receivedCorrelation)
            assertEquals(listOf("", ""), upgrades)
            assertEquals(listOf("", "{}"), bodies)
        }
    }

    @Test
    fun `transport streams frames and propagates downstream cancellation`() = server({ exchange ->
        exchange.sendResponseHeaders(200, 0)
        exchange.responseBody.write("{\"type\":\"message.delta\"}\n".toByteArray())
    }) { gateway ->
        val lines = mutableListOf<String>()
        gateway.stream("{}", 3, lines::add)
        assertEquals(listOf("{\"type\":\"message.delta\"}"), lines)
        assertThrows(java.io.IOException::class.java) {
            gateway.stream("{}", 3) { throw java.io.IOException("synthetic disconnect") }
        }
    }

    @Test
    fun `total deadline bounds a stalled response body with a stable timeout code`() = server({ exchange ->
        exchange.sendResponseHeaders(200, 0)
        exchange.responseBody.write(" ".toByteArray())
        exchange.responseBody.flush()
        Thread.sleep(3000)
    }) { gateway ->
        val started = System.nanoTime()
        val failure = assertThrows(AiFailure::class.java) { gateway.stream("{}", 1) {} }
        assertEquals("REQUEST_TIMEOUT", failure.code)
        assertTrue(java.time.Duration.ofNanos(System.nanoTime() - started).seconds < 3)
    }
}
