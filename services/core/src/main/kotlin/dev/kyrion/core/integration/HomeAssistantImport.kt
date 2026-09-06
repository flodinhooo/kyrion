package dev.kyrion.core.integration

import dev.kyrion.core.activity.*
import dev.kyrion.core.capability.*
import dev.kyrion.core.home.Room
import dev.kyrion.core.home.RoomRepository
import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import dev.kyrion.core.security.UnauthenticatedException
import jakarta.servlet.http.HttpServletRequest
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.support.TransactionTemplate
import org.springframework.web.bind.annotation.*
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.util.Locale
import java.util.UUID

const val HOME_ASSISTANT_PROVIDER = "home_assistant"

data class ImportedDeviceState(
    val connectionId: UUID,
    val hardwareName: String,
    val state: DeviceStateView,
    val capabilities: List<String>
)

data class HomeAssistantSyncStatus(
    val configured: Boolean, val status: String, val lastAttemptAt: Instant? = null,
    val lastSuccessAt: Instant? = null, val reason: String? = null, val correlationId: UUID? = null,
    val lastError: String? = null,
)

data class HomeAssistantSyncResult(val imported: Int, val correlationId: UUID, val reason: String? = null)

interface ImportedDeviceRepository {
    fun all(ownerId: UUID): List<ImportedDeviceState>
    fun save(ownerId: UUID, state: ImportedDeviceState)
}

@Repository
class JdbcImportedDeviceRepository(private val jdbc: JdbcClient) : ImportedDeviceRepository {
    override fun all(ownerId: UUID): List<ImportedDeviceState> =
        jdbc.sql("SELECT * FROM home_assistant_device WHERE owner_id=:owner")
            .param("owner", ownerId).query { rs, _ ->
                ImportedDeviceState(
                    rs.getObject("connection_id", UUID::class.java),
                    rs.getString("hardware_name"), DeviceStateView(
                        rs.getObject("on_state", Boolean::class.javaObjectType),
                        null,
                        null,
                        null,
                        null,
                        occupancy = rs.getObject("occupancy", Boolean::class.javaObjectType),
                        battery = rs.getObject("battery", Double::class.javaObjectType),
                        temperatureCelsius = rs.getObject("temperature_celsius", Double::class.javaObjectType),
                        relativeHumidity = rs.getObject("relative_humidity", Double::class.javaObjectType),
                        measuredAt = rs.getTimestamp("measured_at")?.toInstant()
                    ),
                    rs.getString("capabilities").split(',').filter { it.isNotBlank() })
            }.list()

    override fun save(ownerId: UUID, state: ImportedDeviceState) {
        jdbc.sql(
            """INSERT INTO home_assistant_device(connection_id,owner_id,hardware_name,on_state,temperature_celsius,relative_humidity,battery,occupancy,measured_at,capabilities)
            VALUES(:id,:owner,:hardware,:on,:temperature,:humidity,:battery,:occupancy,:measured,:capabilities) ON CONFLICT(connection_id) DO UPDATE SET
            hardware_name=EXCLUDED.hardware_name,on_state=EXCLUDED.on_state,temperature_celsius=EXCLUDED.temperature_celsius,
            relative_humidity=EXCLUDED.relative_humidity,battery=EXCLUDED.battery,occupancy=EXCLUDED.occupancy,
            measured_at=EXCLUDED.measured_at,capabilities=EXCLUDED.capabilities
            WHERE home_assistant_device.owner_id=EXCLUDED.owner_id"""
        )
            .param("id", state.connectionId).param("owner", ownerId).param("hardware", state.hardwareName)
            .param("on", state.state.on, java.sql.Types.BOOLEAN)
            .param("temperature", state.state.temperatureCelsius, java.sql.Types.DOUBLE)
            .param("humidity", state.state.relativeHumidity, java.sql.Types.DOUBLE)
            .param("battery", state.state.battery, java.sql.Types.DOUBLE)
            .param("occupancy", state.state.occupancy, java.sql.Types.BOOLEAN)
            .param("measured", state.state.measuredAt?.let(Timestamp::from), java.sql.Types.TIMESTAMP)
            .param("capabilities", state.capabilities.joinToString(",")).update()
    }
}

/** Exact name mapping deliberately does not use the Voice resolver's synonyms. */
internal fun importedRoom(area: String?, rooms: List<Room>): UUID? {
    val name = area?.trim()?.lowercase(Locale.ROOT)?.takeIf { it.isNotEmpty() } ?: return null
    return rooms.singleOrNull { it.name.trim().lowercase(Locale.ROOT) == name }?.id
}

@Service
class HomeAssistantReconciler(
    private val connections: IntegrationConnectionRepository,
    private val rooms: RoomRepository,
    private val observations: DeviceObservationRepository,
    private val readings: ImportedDeviceRepository,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun reconcile(ownerId: UUID, devices: List<HomeAssistantDevice>) {
        val now = clock.instant()
        val existing = connections.findAll(ownerId).filter { it.provider == HOME_ASSISTANT_PROVIDER }
            .associateBy { it.endpointHost }
        val ownerRooms = rooms.all(ownerId)
        devices.forEach { device ->
            val connection = existing[device.externalId]?.also {
                connections.update(ownerId, it.id, device.name, device.deviceClass, now)
            } ?: connections.save(
                IntegrationConnection(
                    UUID.randomUUID(),
                    ownerId,
                    HOME_ASSISTANT_PROVIDER,
                    device.name,
                    device.externalId,
                    byteArrayOf(),
                    byteArrayOf(),
                    1,
                    now,
                    now,
                    deviceClass = device.deviceClass
                )
            )
            check(rooms.assignConnection(ownerId, connection.id, importedRoom(device.area, ownerRooms)))
            readings.save(
                ownerId,
                ImportedDeviceState(connection.id, device.hardwareName, device.state, device.capabilities)
            )
            observations.save(DeviceObservation(connection.id, ownerId, device.availability, now))
        }
        val present = devices.map { it.externalId }.toSet()
        existing.filterKeys { it !in present }.values.forEach {
            observations.save(DeviceObservation(it.id, ownerId, DeviceAvailability.UNKNOWN, now))
        }
    }
}

@Service
class HomeAssistantImportService(
    private val configuration: HomeAssistantConfiguration,
    private val gateway: HomeAssistantGateway,
    private val reconciler: HomeAssistantReconciler,
    private val jdbc: JdbcClient,
    private val transactions: TransactionTemplate,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
) {
    fun status(ownerId: UUID): HomeAssistantSyncStatus {
        if (!configuration.configured(ownerId)) return HomeAssistantSyncStatus(
            false,
            "unknown",
            reason = "configuration_missing"
        )
        return jdbc.sql("SELECT * FROM home_assistant_sync WHERE owner_id=:owner").param("owner", ownerId)
            .query { rs, _ ->
                val reason = rs.getString("reason")
                val attempted = rs.getTimestamp("attempted_at").toInstant()
                val success = rs.getTimestamp("succeeded_at")?.toInstant()
                val stale = attempted.isBefore(clock.instant().minus(DeviceCatalogService.OBSERVATION_TTL))
                HomeAssistantSyncStatus(
                    true,
                    if (stale) "unknown" else if (reason == "dependency_unreachable") "offline" else if (reason != null) "degraded" else "healthy",
                    attempted,
                    success,
                    if (stale) "stale_observation" else reason,
                    rs.getObject("correlation_id", UUID::class.java), reason,
                )
            }.optional().orElse(HomeAssistantSyncStatus(true, "unknown", reason = "no_observation"))
    }

    fun sync(ownerId: UUID): HomeAssistantSyncResult {
        if (!configuration.configured(ownerId)) throw HomeAssistantException("configuration_missing")
        val correlationId = UUID.randomUUID()
        // Serialize the snapshot fetch as well as writes across Core processes.
        return transactions.execute {
            jdbc.sql("SELECT id FROM user_account WHERE id=:owner FOR UPDATE").param("owner", ownerId)
                .query(UUID::class.java).single()
            var reason: String? = null
            val devices = try {
                gateway.snapshot(ownerId)
            } catch (exception: HomeAssistantException) {
                reason = exception.code; null
            }
            if (devices != null) reconciler.reconcile(ownerId, devices)
            val now = Timestamp.from(clock.instant())
            jdbc.sql(
                """INSERT INTO home_assistant_sync(owner_id,attempted_at,succeeded_at,reason,correlation_id)
                VALUES(:owner,:now,:success,:reason,:correlation) ON CONFLICT(owner_id) DO UPDATE SET
                attempted_at=EXCLUDED.attempted_at,succeeded_at=COALESCE(EXCLUDED.succeeded_at,home_assistant_sync.succeeded_at),
                reason=EXCLUDED.reason,correlation_id=EXCLUDED.correlation_id"""
            )
                .param("owner", ownerId).param("now", now).param("success", if (devices != null) now else null)
                .param("reason", reason).param("correlation", correlationId).update()
            activity.record(
                ActivityCategory.INTEGRATION, "integration.home_assistant.synced",
                if (devices != null) ActivityStatus.SUCCEEDED else ActivityStatus.FAILED, ActivityActorType.USER,
                "home_assistant", reason ?: "import.succeeded", ownerId.toString(), correlationId, ownerId
            )
            HomeAssistantSyncResult(devices?.size ?: 0, correlationId, reason)
        }
    }
}

@RestController
@RequestMapping("/v1/integrations/home-assistant")
class HomeAssistantController(private val service: HomeAssistantImportService) {
    @GetMapping
    fun status(request: HttpServletRequest) = service.status(request.ownerId())
    @PostMapping("/sync")
    fun sync(request: HttpServletRequest) = service.sync(request.ownerId())
    private fun HttpServletRequest.ownerId() =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw UnauthenticatedException()

    @ExceptionHandler(HomeAssistantException::class)
    fun error(exception: HomeAssistantException) =
        org.springframework.http.ResponseEntity.status(409).body(mapOf("code" to exception.code))
}
