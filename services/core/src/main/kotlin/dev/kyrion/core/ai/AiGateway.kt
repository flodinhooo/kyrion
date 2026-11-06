package dev.kyrion.core.ai

import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.io.BufferedReader
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

interface AiGateway {
    fun catalog(): AiCatalog
    fun stream(payload: String, timeoutSeconds: Int, receive: (String) -> Unit)
    fun streamTraced(payload: String, timeoutSeconds: Int, correlationId: java.util.UUID, receive: (String) -> Unit) =
        stream(payload, timeoutSeconds, receive)
    fun streamGuarded(payload: String, timeoutSeconds: Int, correlationId: java.util.UUID,
        validateActive: () -> Unit, receive: (String) -> Unit) {
        validateActive()
        streamTraced(payload, timeoutSeconds, correlationId) { line ->
            validateActive()
            receive(line)
        }
    }
}

@Component
class HttpAiGateway(@Value("\${kyrion.ai.base-url:http://127.0.0.1:8000}") url: String) : AiGateway {
    private val base = url.trimEnd('/')
    // Uvicorn's HTTP/1.1 boundary must not receive a cleartext h2c upgrade.
    // With the JDK default HTTP/2 negotiation it can discard the JSON body (422).
    private val client = HttpClient.newBuilder().version(HttpClient.Version.HTTP_1_1)
        .connectTimeout(Duration.ofSeconds(5)).build()
    override fun catalog(): AiCatalog {
        val response = try {
            client.send(
                HttpRequest.newBuilder(URI("$base/v1/models")).timeout(Duration.ofSeconds(12)).GET().build(),
                HttpResponse.BodyHandlers.ofString()
            )
        } catch (_: Exception) {
            throw AiFailure("MODEL_UNAVAILABLE", 503)
        }
        if (response.statusCode() != 200 || response.body().length > 1_000_000) throw AiFailure(
            "MODEL_UNAVAILABLE",
            503
        )
        return try {
            aiJson.readValue(response.body(), AiCatalog::class.java).also { catalog ->
                require(catalog.models.size in 1..200 && catalog.models.map { it.id }
                    .distinct().size == catalog.models.size)
                catalog.models.forEach { model ->
                    require(model.id.length in 1..128 && model.provider in ModelRouter.providers && model.local == (model.provider == "ollama"))
                    require(model.maxOutputTokens in 1..32768 && model.inputCostPerMillion?.signum() != -1 && model.outputCostPerMillion?.signum() != -1)
                }
            }
        } catch (_: Exception) {
            throw AiFailure("MODEL_UNAVAILABLE", 503)
        }
    }

    override fun stream(payload: String, timeoutSeconds: Int, receive: (String) -> Unit) =
        streamTraced(payload, timeoutSeconds, java.util.UUID.randomUUID(), receive)

    override fun streamTraced(payload: String, timeoutSeconds: Int, correlationId: java.util.UUID, receive: (String) -> Unit) {
        streamGuarded(payload, timeoutSeconds, correlationId, {}, receive)
    }

    override fun streamGuarded(payload: String, timeoutSeconds: Int, correlationId: java.util.UUID,
        validateActive: () -> Unit, receive: (String) -> Unit) {
        validateActive()
        val expires = System.nanoTime() + TimeUnit.SECONDS.toNanos(timeoutSeconds.toLong())
        val cancelled = java.util.concurrent.atomic.AtomicReference<Exception?>()
        val body = java.util.concurrent.atomic.AtomicReference<java.io.InputStream?>()
        val finished = java.util.concurrent.atomic.AtomicBoolean(false)
        val pending = client.sendAsync(
                HttpRequest.newBuilder(URI("$base/v1/chat/stream")).timeout(Duration.ofSeconds(timeoutSeconds.toLong()))
                    .header("X-Kyrion-Correlation-Id", correlationId.toString())
                    .header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(payload))
                    .build(),
                HttpResponse.BodyHandlers.ofInputStream()
            )
        // Check explicit captured authority even when the provider sends no headers,
        // a partial frame, or no further events. Never depend on provider activity.
        val monitor = Thread.ofVirtual().name("ai-authority-watch").start {
            try {
                while (!finished.get()) {
                    Thread.sleep(250)
                    if (finished.get()) break
                    validateActive()
                }
            } catch (_: InterruptedException) {
                // Normal stream completion interrupts only this owned monitor.
            } catch (failure: Exception) {
                cancelled.compareAndSet(null, failure)
                pending.cancel(true)
                runCatching { body.get()?.close() }
            }
        }
        try {
            val response = try {
                pending.get()
            } catch (failure: Exception) {
                cancelled.get()?.let { throw it }
                if (failure.cause is java.net.http.HttpTimeoutException) throw AiFailure("REQUEST_TIMEOUT", 504)
                throw failure
            }
            body.set(response.body())
            response.body().use { input ->
                cancelled.get()?.let { throw it }
                val timedOut = java.util.concurrent.atomic.AtomicBoolean(false)
                val timer = deadline.schedule(
                    { timedOut.set(true); runCatching { input.close() } },
                    (expires - System.nanoTime()).coerceAtLeast(1), TimeUnit.NANOSECONDS
                )
                try {
                    if (response.statusCode() != 200) {
                        val code = runCatching { aiJson.readTree(input.readNBytes(4096)).path("code").asText() }.getOrNull()
                        if (timedOut.get()) throw AiFailure("REQUEST_TIMEOUT", 504)
                        throw AiFailure(code?.takeIf { it in safeAiErrors } ?: "MODEL_UNAVAILABLE", 503)
                    }
                    // Bound each line before allocating an untrusted whole upstream frame.
                    val reader = BufferedReader(input.reader(Charsets.UTF_8))
                    val line = StringBuilder()
                    while (true) {
                        val ch = reader.read()
                        cancelled.get()?.let { throw it }
                        if (timedOut.get()) throw AiFailure("REQUEST_TIMEOUT", 504)
                        if (ch == -1) {
                            if (line.isNotEmpty()) { validateActive(); receive(line.toString()) }; break
                        }
                        if (ch == '\n'.code) {
                            if (line.isNotEmpty()) { validateActive(); receive(line.toString()) }; line.setLength(0)
                        } else if (ch != '\r'.code) {
                            line.append(ch.toChar()); if (line.length > 1_000_000) throw AiFailure("STREAM_FAILED", 502)
                        }
                    }
                } catch (error: java.io.IOException) {
                    cancelled.get()?.let { throw it }
                    if (timedOut.get()) throw AiFailure("REQUEST_TIMEOUT", 504)
                    throw error
                } finally {
                    timer.cancel(false)
                }
            }
        } finally {
            finished.set(true)
            monitor.interrupt()
            pending.cancel(true)
            runCatching { body.get()?.close() }
        }
    }

    companion object {
        private val deadline = Executors.newSingleThreadScheduledExecutor { runnable ->
            Thread(runnable, "ai-deadline").apply {
                isDaemon = true
            }
        }
    }
}

val safeAiErrors = setOf(
    "MODEL_UNAVAILABLE",
    "PROVIDER_NOT_CONFIGURED",
    "CLOUD_NOT_ALLOWED",
    "MODEL_DISABLED",
    "CAPABILITY_UNSUPPORTED",
    "PROVIDER_AUTH_FAILED",
    "RATE_LIMITED",
    "REQUEST_TIMEOUT",
    "CONTEXT_NOT_ALLOWED",
    "CONTEXT_LIMIT_EXCEEDED",
    "TOOL_CALL_INVALID",
    "PROVIDER_REFUSED",
    "OUTPUT_LIMIT_REACHED",
    "STREAM_FAILED",
    "INVALID_REQUEST"
)
