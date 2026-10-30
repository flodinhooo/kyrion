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
}

@Component
class HttpAiGateway(@Value("\${kyrion.ai.base-url:http://127.0.0.1:8000}") url: String) : AiGateway {
    private val base = url.trimEnd('/')
    private val client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build()
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

    override fun stream(payload: String, timeoutSeconds: Int, receive: (String) -> Unit) {
        val response = client.send(
            HttpRequest.newBuilder(URI("$base/v1/chat/stream")).timeout(Duration.ofSeconds(timeoutSeconds.toLong()))
                .header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(payload)).build(),
            HttpResponse.BodyHandlers.ofInputStream()
        )
        response.body().use { input ->
            if (response.statusCode() != 200) {
                val code = runCatching { aiJson.readTree(input.readNBytes(4096)).path("code").asText() }.getOrNull()
                throw AiFailure(code?.takeIf { it in safeAiErrors } ?: "MODEL_UNAVAILABLE", 503)
            }
            val timer = deadline.schedule({ runCatching { input.close() } }, timeoutSeconds.toLong(), TimeUnit.SECONDS)
            try {
                // Bound each line before allocating an untrusted whole upstream frame.
                val reader = BufferedReader(input.reader(Charsets.UTF_8))
                val line = StringBuilder()
                while (true) {
                    val ch = reader.read()
                    if (ch == -1) {
                        if (line.isNotEmpty()) receive(line.toString()); break
                    }
                    if (ch == '\n'.code) {
                        if (line.isNotEmpty()) receive(line.toString()); line.setLength(0)
                    } else if (ch != '\r'.code) {
                        line.append(ch.toChar()); if (line.length > 1_000_000) throw AiFailure("STREAM_FAILED", 502)
                    }
                }
            } finally {
                timer.cancel(false)
            }
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
