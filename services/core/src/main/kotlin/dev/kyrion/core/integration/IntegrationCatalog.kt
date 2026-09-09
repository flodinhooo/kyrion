package dev.kyrion.core.integration

import dev.kyrion.core.security.workspaceOwnerId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.*
import org.springframework.stereotype.Service
import java.time.Instant
import java.util.UUID

enum class IntegrationLocality { LOCAL, CLOUD }
enum class IntegrationAuthType { NONE, OAUTH, API_KEY, CREDENTIALS, LOCAL_DISCOVERY, DEVICE_FLOW, CUSTOM }
enum class ProviderAvailability { LIVE, IN_DEVELOPMENT, PLANNED }
enum class ConnectionStatus { CONNECTED, DISCONNECTED, CONFIGURATION_REQUIRED, DEGRADED, ERROR }

data class IntegrationCapability(
    val id: String,
    val name: String,
    val description: String,
)

data class IntegrationProvider(
    val id: String,
    val name: String,
    val description: String,
    val locality: IntegrationLocality,
    val authentication: IntegrationAuthType,
    val availability: ProviderAvailability,
    val capabilities: List<IntegrationCapability>,
)

data class IntegrationConnectionSummary(
    val providerId: String,
    val connectionId: UUID,
    val status: ConnectionStatus,
    val displayIdentity: String,
    val enabledCapabilities: List<String>,
    val availableCapabilities: List<String>,
    val createdAt: Instant,
    val updatedAt: Instant,
    val health: String? = null,
)

@Service
class IntegrationCatalogService(
    private val connections: IntegrationConnectionRepository,
    private val spotify: SpotifyIntegrationService,
    private val grants: JdbcIntegrationCapabilityGrantRepository,
) {
    private val providers = listOf(
        IntegrationProvider("nanoleaf", "Nanoleaf", "Local Nanoleaf panels", IntegrationLocality.LOCAL, IntegrationAuthType.LOCAL_DISCOVERY, ProviderAvailability.LIVE,
            listOf(IntegrationCapability("light.read", "Read lights", "Read light state"), IntegrationCapability("light.control", "Control lights", "Control power and brightness"), IntegrationCapability("light.color", "Color", "Control color and temperature"))),
        IntegrationProvider("zigbee", "Zigbee", "Local Zigbee devices through a gateway", IntegrationLocality.LOCAL, IntegrationAuthType.LOCAL_DISCOVERY, ProviderAvailability.LIVE,
            listOf(IntegrationCapability("smart-home.devices", "Devices", "Discover Zigbee devices"), IntegrationCapability("smart-home.control", "Control", "Control approved devices"))),
        IntegrationProvider("spotify", "Spotify", "Spotify Connect playback", IntegrationLocality.CLOUD, IntegrationAuthType.OAUTH, ProviderAvailability.LIVE,
            listOf(IntegrationCapability("media.playback", "Playback", "Control Spotify Connect playback"), IntegrationCapability("media.library", "Library", "Read supported playlists"))),
        IntegrationProvider("google", "Google", "Google services", IntegrationLocality.CLOUD, IntegrationAuthType.OAUTH, ProviderAvailability.PLANNED, emptyList()),
        IntegrationProvider("jellyfin", "Jellyfin", "Local media server", IntegrationLocality.LOCAL, IntegrationAuthType.API_KEY, ProviderAvailability.PLANNED, emptyList()),
    )

    fun providers() = providers
    fun provider(id: String) = providers.firstOrNull { it.id == id }
    fun connections(ownerId: UUID): List<IntegrationConnectionSummary> = connections.findAll(ownerId).filter { it.provider != "spotify" }.map { summary(it) } + listOfNotNull(spotifySummary(ownerId))
    fun connection(ownerId: UUID, id: UUID) = connections(ownerId).firstOrNull { it.connectionId == id }

    private fun spotifySummary(ownerId: UUID): IntegrationConnectionSummary? {
        val status = spotify.status(ownerId)
        if (!status.connected) return null
        val definition = provider("spotify")!!
        val connection = connections.findAll(ownerId).firstOrNull { it.provider == "spotify" } ?: return null
        return summary(connection, definition, status.accountName ?: connection.displayName)
    }

    private fun summary(connection: IntegrationConnection): IntegrationConnectionSummary {
        return summary(connection, provider(connection.provider), connection.displayName)
    }
    private fun summary(connection: IntegrationConnection, definition: IntegrationProvider?, identity: String): IntegrationConnectionSummary {
        val capabilities = definition?.capabilities?.map { it.id }.orEmpty()
        val enabled = grants.findAll(connection.ownerId, connection.id).filter { it.granted }.map { it.capability }.filter { it in capabilities }
        return IntegrationConnectionSummary(connection.provider, connection.id, ConnectionStatus.CONNECTED, identity, enabled, capabilities, connection.createdAt, connection.updatedAt)
    }
}

@RestController
@RequestMapping("/v1/integration-catalog")
class IntegrationCatalogController(private val service: IntegrationCatalogService) {
    @GetMapping("/providers") fun providers() = service.providers()
    @GetMapping("/providers/{id}") fun provider(@PathVariable id: String) = service.provider(id) ?: throw ProviderNotFoundException()
    @GetMapping("/connections") fun connections(request: HttpServletRequest) = service.connections(request.workspaceOwnerId())
    @GetMapping("/connections/{id}") fun connection(@PathVariable id: UUID, request: HttpServletRequest) = service.connection(request.workspaceOwnerId(), id) ?: throw ConnectionNotFoundException()
}

class ProviderNotFoundException : RuntimeException()
class ConnectionNotFoundException : RuntimeException()

@RestControllerAdvice
class IntegrationCatalogErrorHandler {
    @ExceptionHandler(ProviderNotFoundException::class, ConnectionNotFoundException::class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    fun notFound() = mapOf("code" to "INTEGRATION_NOT_FOUND")
}
