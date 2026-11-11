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

class HomeAssistantConnectionConfig(
    val baseUrl: String,
    val accessToken: String,
) {
    override fun toString() = "HomeAssistantConnectionConfig(baseUrl=$baseUrl, accessToken=<redacted>)"
}

@Component
class HomeAssistantDevelopmentConfiguration(
    @Value("\${KYRION_HA_URL:}") private val url: String,
    @Value("\${KYRION_HA_TOKEN:}") private val token: String,
    @Value("\${KYRION_HA_OWNER_ID:}") private val owner: String,
) {
    fun configured(ownerId: UUID) = owner == ownerId.toString() && url.isNotBlank() && token.isNotBlank()
    fun connection(ownerId: UUID): HomeAssistantConnectionConfig {
        if (!configured(ownerId)) throw HomeAssistantException("configuration_missing")
        return HomeAssistantConnectionConfig(url, token)
    }

    /** Compatibility adapter for the existing development-only gateway tests. */
    fun request(ownerId: UUID, body: String): HttpRequest = homeAssistantRequest(connection(ownerId), body)
}

typealias HomeAssistantConfiguration = HomeAssistantDevelopmentConfiguration

internal fun homeAssistantRequest(config: HomeAssistantConnectionConfig, body: String, path: String = "/api/template", get: Boolean = false): HttpRequest {
        val allowed = if (get) Regex("/api/states/(?:light|switch)\\.[a-z0-9_]{1,240}").matches(path)
            else path == "/api/template" || Regex("/api/services/(?:light|switch)/(?:turn_on|turn_off)").matches(path)
        if (!allowed) throw HomeAssistantException("control_unsupported")
        val uri = try {
            URI(config.baseUrl)
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
            ) || uri.port !in -1..65535 || uri.port == 0 || config.accessToken.isBlank() || config.accessToken.length > 8192 || config.accessToken.any { it == '\r' || it == '\n' }
        ) {
            throw HomeAssistantException("configuration_invalid")
        }
        val builder = HttpRequest.newBuilder(URI(config.baseUrl.trimEnd('/') + path))
            .timeout(Duration.ofSeconds(10)).header("Authorization", "Bearer ${config.accessToken}")
            .header("Content-Type", "application/json")
        return (if (get) builder.GET() else builder.POST(HttpRequest.BodyPublishers.ofString(body))).build()
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
    val entities: List<HomeAssistantEntity> = emptyList(),
)

data class HomeAssistantEntity(val id: String, val name: String, val state: String) {
    val supportsPower: Boolean get() = id.startsWith("light.") || id.startsWith("switch.")
}
data class HomeAssistantPowerConfirmation(val on: Boolean, val updatedAt: Instant?)

interface HomeAssistantGateway {
    fun snapshot(ownerId: UUID): List<HomeAssistantDevice>
}

@Component
class HomeAssistantClient(
    private val configuration: HomeAssistantDevelopmentConfiguration,
    private val mapper: ObjectMapper = com.fasterxml.jackson.module.kotlin.jacksonObjectMapper(),
    private val http: HttpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3))
        .followRedirects(HttpClient.Redirect.NEVER).build(),
) : HomeAssistantGateway {

    override fun snapshot(ownerId: UUID): List<HomeAssistantDevice> {
        return snapshot(configuration.connection(ownerId))
    }

    fun snapshot(config: HomeAssistantConnectionConfig, selected: Map<String, Set<String>>? = null): List<HomeAssistantDevice> {
        val request = homeAssistantRequest(config, mapper.writeValueAsString(mapOf("template" to TEMPLATE)))
        val root = exchange(request)
        val all = parse(root)
        if (selected == null) return all
        val filtered = mapper.createArrayNode()
        root.forEach { row ->
            if (selected[row.path("id").asText()]?.contains(row.path("entity").asText()) == true) filtered.add(row)
        }
        return parse(filtered)
    }

    fun power(config: HomeAssistantConnectionConfig, entity: String, on: Boolean): HomeAssistantPowerConfirmation {
        if (!entity.matches(Regex("(?:light|switch)\\.[a-z0-9_]{1,240}"))) throw HomeAssistantException("control_unsupported")
        val service = if (on) "turn_on" else "turn_off"
        exchange(homeAssistantRequest(config, mapper.writeValueAsString(mapOf("entity_id" to entity)), "/api/services/${entity.substringBefore('.')}/$service"))
        repeat(3) { attempt ->
            val state = exchange(homeAssistantRequest(config, "", "/api/states/$entity", get = true))
            if (state.path("entity_id").asText() != entity) throw HomeAssistantException("invalid_response")
            if (state.path("state").asText() == if (on) "on" else "off") {
                return HomeAssistantPowerConfirmation(on, runCatching { Instant.parse(state.path("last_updated").asText()) }.getOrNull())
            }
            if (attempt < 2) try { Thread.sleep(150) } catch (_: InterruptedException) {
                Thread.currentThread().interrupt(); throw HomeAssistantException("dependency_unreachable")
            }
        }
        throw HomeAssistantException("control_not_confirmed")
    }

    private fun exchange(request: HttpRequest): JsonNode {
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
                return mapper.readTree(bytes)
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
                ?.takeIf { it.isNotEmpty() && it.length <= 160 && it.none(Char::isISOControl) }

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
            val contact = entities.filter { it.path("entity").asText().startsWith("binary_sensor.") && it.path("class").asText() in setOf("door", "window", "opening") }
            val on = (power.singleOrNull() ?: contact.singleOrNull())?.path("state")?.asText()?.let {
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
            val light = power.singleOrNull()?.takeIf { it.path("entity").asText().startsWith("light.") && it.path("state").asText() in setOf("on", "off") }
            fun lightNumber(key: String, min: Double, max: Double): Double? = light?.path(key)?.takeIf { it.isNumber }?.asDouble()?.takeIf { it.isFinite() && it in min..max }
            val brightness = lightNumber("brightness", 0.0, 255.0)?.let { kotlin.math.round(it * 100 / 255).toInt() }
            val hue = lightNumber("hue", 0.0, 360.0)
            val saturation = lightNumber("saturation", 0.0, 100.0)
            if (power.size > 1 || contact.size > 1 || occupancyEntities.size > 1) invalid = true
            val times = entities.mapNotNull { runCatching { Instant.parse(it.path("updated").asText()) }.getOrNull() }
            if (times.size != entities.size) invalid = true
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
                    on, brightness, hue, saturation, null, battery = battery, occupancy = occupancy,
                    temperatureCelsius = temperature, relativeHumidity = humidity, measuredAt = times.minOrNull()
                ),
                buildList {
                    if (entities.any { it.path("class").asText() == "temperature" }) add("temperature.read")
                    if (entities.any { it.path("class").asText() == "humidity" }) add("humidity.read")
                    if (entities.any { it.path("class").asText() == "battery" }) add("battery.read")
                    if (power.size == 1) add("power.read")
                    if (contact.size == 1 && power.isEmpty()) add("contact.read")
                    if (occupancyEntities.size == 1) add("occupancy.read")
                },
                entities.map { entity ->
                    val entityId = entity.path("entity").asText()
                    if (!entityId.matches(Regex("(?:light|switch|sensor|binary_sensor)\\.[a-z0-9_]{1,240}"))) throw HomeAssistantException("invalid_response")
                    HomeAssistantEntity(entityId, entity.path("entityName").asText().takeIf { it.isNotBlank() && it.length <= 240 && it.none(Char::isISOControl) } ?: entityId.substringAfter('.'), entity.path("state").asText())
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
            {% set ns.rows = ns.rows + [dict(id=id, entity=s.entity_id, entityName=s.attributes.get('friendly_name'),
              name=device_attr(id, 'name_by_user') or device_attr(id, 'name'),
              area=area_name(id), manufacturer=device_attr(id, 'manufacturer'), model=device_attr(id, 'model'),
              state=s.state, class=s.attributes.get('device_class'), unit=s.attributes.get('unit_of_measurement'), updated=s.last_updated.isoformat(),
              brightness=s.attributes.get('brightness'),
              hue=(s.attributes.get('hs_color') or [none, none])[0],
              saturation=(s.attributes.get('hs_color') or [none, none])[1])] %}
            {% endif %}{% endfor %}{{ ns.rows | to_json }}
        """.trimIndent()
    }
}
