package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.databind.ObjectMapper
import dev.kyrion.core.capability.DeviceAvailability
import dev.kyrion.core.capability.DeviceStateView
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration
import java.time.Instant
import java.util.UUID

class HomeAssistantException(val code: String) : RuntimeException(code)

@Component
class HomeAssistantConfiguration(
    @Value("\${KYRION_HA_URL:}") private val url: String,
    @Value("\${KYRION_HA_TOKEN:}") private val token: String,
    @Value("\${KYRION_HA_OWNER_ID:}") private val owner: String,
) {
    fun configured(ownerId: UUID) = owner == ownerId.toString() && url.isNotBlank() && token.isNotBlank()
    fun request(ownerId: UUID, body: String): HttpRequest {
        if (!configured(ownerId)) throw HomeAssistantException("configuration_missing")
        val uri = try {
            URI(url)
        } catch (_: Exception) {
            throw HomeAssistantException("configuration_invalid")
        }
        // Literal private IPv4 avoids DNS rebinding and keeps this local-only slice bounded.
        try {
            privateNetworkIpv4(uri.host ?: "")
        } catch (_: RuntimeException) {
            throw HomeAssistantException("configuration_invalid")
        }
        if (uri.scheme !in setOf(
                "http",
                "https"
            ) || uri.userInfo != null || uri.query != null || uri.fragment != null ||
            uri.path !in setOf(
                "",
                "/"
            ) || uri.port !in -1..65535 || uri.port == 0 || token.any { it == '\r' || it == '\n' }
        ) {
            throw HomeAssistantException("configuration_invalid")
        }
        return HttpRequest.newBuilder(URI(url.trimEnd('/') + "/api/template"))
            .timeout(Duration.ofSeconds(10)).header("Authorization", "Bearer $token")
            .header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(body)).build()
    }
}

data class HomeAssistantDevice(
    val externalId: String,
    val name: String,
    val area: String?,
    val hardwareName: String,
    val deviceClass: DeviceClass,
    val availability: DeviceAvailability,
    val state: DeviceStateView,
    val capabilities: List<String>,
)

interface HomeAssistantGateway {
    fun snapshot(ownerId: UUID): List<HomeAssistantDevice>
}

@Component
class HomeAssistantClient(
    private val configuration: HomeAssistantConfiguration,
    private val mapper: ObjectMapper = com.fasterxml.jackson.module.kotlin.jacksonObjectMapper(),
    private val http: HttpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3))
        .followRedirects(HttpClient.Redirect.NEVER).build(),
) : HomeAssistantGateway {

    override fun snapshot(ownerId: UUID): List<HomeAssistantDevice> {
        val request = configuration.request(ownerId, mapper.writeValueAsString(mapOf("template" to TEMPLATE)))
        try {
            val response = http.send(request, HttpResponse.BodyHandlers.ofInputStream())
            response.body().use { stream ->
                if (response.statusCode() in setOf(401, 403)) throw HomeAssistantException("authentication_failed")
                if (response.statusCode() != 200) throw HomeAssistantException("dependency_error")
                val reading = java.util.concurrent.CompletableFuture.supplyAsync { stream.readNBytes(MAX_BYTES + 1) }
                val bytes = try {
                    reading.get(10, java.util.concurrent.TimeUnit.SECONDS)
                } catch (_: java.util.concurrent.TimeoutException) {
                    reading.cancel(true); throw HomeAssistantException("dependency_unreachable")
                } catch (_: java.util.concurrent.ExecutionException) {
                    throw HomeAssistantException("dependency_unreachable")
                }
                if (bytes.size > MAX_BYTES) throw HomeAssistantException("invalid_response")
                return parse(mapper.readTree(bytes))
            }
        } catch (exception: HomeAssistantException) {
            throw exception
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt(); throw HomeAssistantException("dependency_unreachable")
        } catch (_: com.fasterxml.jackson.core.JacksonException) {
            throw HomeAssistantException("invalid_response")
        } catch (_: java.io.IOException) {
            throw HomeAssistantException("dependency_unreachable")
        } catch (_: RuntimeException) {
            throw HomeAssistantException("invalid_response")
        }
    }

    internal fun parse(root: JsonNode): List<HomeAssistantDevice> {
        if (!root.isArray || root.size() > 2000) throw HomeAssistantException("invalid_response")
        val rows = root.toList()
        if (rows.any {
                !it.isObject || !it.path("id").asText().matches(Regex("[a-fA-F0-9]{32}")) ||
                    !it.path("entity").asText().matches(Regex("(sensor|binary_sensor|light|switch)\\.[a-z0-9_]+")) ||
                    !it.path("state").isTextual
            }) throw HomeAssistantException("invalid_response")
        if (rows.map { it.path("entity").asText() }
                .distinct().size != rows.size) throw HomeAssistantException("invalid_response")
        val groups = rows.groupBy { it.path("id").asText() }
        if (groups.size > 250) throw HomeAssistantException("invalid_response")
        return groups.toSortedMap().map { (id, entities) ->
            val first = entities.first()
            fun label(key: String): String? = first.path(key).takeIf { it.isTextual }?.asText()?.trim()
                ?.takeIf { it.isNotEmpty() && it.length <= 160 }

            val name = label("name") ?: "Home Assistant"
            var invalid = label("name") == null
            fun number(kind: String, min: Double, max: Double): Double? {
                val candidates = entities.filter { it.path("class").asText() == kind }
                if (candidates.size != 1) {
                    if (candidates.size > 1) invalid = true; return null
                }
                val row = candidates.single()
                if (row.path("state").asText() in setOf("unavailable", "unknown")) return null
                var value = row.path("state").asText().toDoubleOrNull()
                val unit = row.path("unit").asText()
                if (kind == "temperature" && unit == "°F") value = value?.let { (it - 32) * 5 / 9 }
                else if (kind == "temperature" && unit != "°C" || kind in setOf(
                        "humidity",
                        "battery"
                    ) && unit != "%"
                ) value = null
                if (value == null || !value.isFinite() || value !in min..max) {
                    invalid = true; return null
                }
                return value
            }

            val temperature = number("temperature", -100.0, 150.0)
            val humidity = number("humidity", 0.0, 100.0)
            val battery = number("battery", 0.0, 100.0)
            val power = entities.filter { it.path("entity").asText().substringBefore('.') in setOf("light", "switch") }
            val on = power.singleOrNull()?.path("state")?.asText()?.let {
                when (it) {
                    "on" -> true; "off" -> false; else -> null
                }
            }
            val occupancyEntities =
                entities.filter { it.path("class").asText() in setOf("occupancy", "motion", "presence") }
            val occupancy = occupancyEntities.singleOrNull()?.path("state")?.asText()?.let {
                when (it) {
                    "on" -> true; "off" -> false; else -> null
                }
            }
            val times = entities.mapNotNull { runCatching { Instant.parse(it.path("updated").asText()) }.getOrNull() }
            val availability = when {
                entities.all { it.path("state").asText() == "unavailable" } -> DeviceAvailability.OFFLINE
                entities.all {
                    it.path("state").asText() in setOf(
                        "unknown",
                        "unavailable"
                    )
                } -> DeviceAvailability.UNKNOWN

                invalid || entities.any {
                    it.path("state").asText() in setOf(
                        "unknown",
                        "unavailable"
                    )
                } -> DeviceAvailability.DEGRADED

                else -> DeviceAvailability.ONLINE
            }
            HomeAssistantDevice(
                id,
                name,
                label("area"),
                listOfNotNull(label("manufacturer"), label("model")).joinToString(" ").ifBlank { "Home Assistant" },
                if (power.any {
                        it.path("entity").asText().startsWith("light.")
                    }) DeviceClass.LIGHT else if (power.isNotEmpty()) DeviceClass.SWITCH else DeviceClass.SENSOR,
                availability,
                DeviceStateView(
                    on, null, null, null, null, battery = battery, occupancy = occupancy,
                    temperatureCelsius = temperature, relativeHumidity = humidity, measuredAt = times.minOrNull()
                ),
                buildList {
                    if (entities.any { it.path("class").asText() == "temperature" }) add("temperature.read")
                    if (entities.any { it.path("class").asText() == "humidity" }) add("humidity.read")
                    if (entities.any { it.path("class").asText() == "battery" }) add("battery.read")
                    if (power.size == 1) add("power.read")
                    if (occupancyEntities.size == 1) add("occupancy.read")
                })
        }
    }

    companion object {
        private const val MAX_BYTES = 2_000_000

        // Fixed read-only template: no service calls, events, HA users or arbitrary attributes.
        val TEMPLATE = """
            {% set ns = namespace(rows=[]) %}
            {% for s in states if s.domain in ['sensor', 'binary_sensor', 'light', 'switch'] %}
            {% set id = device_id(s.entity_id) %}
            {% if id %}
            {% set ns.rows = ns.rows + [dict(id=id, entity=s.entity_id,
              name=device_attr(id, 'name_by_user') or device_attr(id, 'name'),
              area=area_name(id), manufacturer=device_attr(id, 'manufacturer'), model=device_attr(id, 'model'),
              state=s.state, class=s.attributes.get('device_class'), unit=s.attributes.get('unit_of_measurement'), updated=s.last_updated.isoformat())] %}
            {% endif %}{% endfor %}{{ ns.rows | to_json }}
        """.trimIndent()
    }
}
