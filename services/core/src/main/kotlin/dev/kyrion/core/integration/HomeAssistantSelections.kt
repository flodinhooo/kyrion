package dev.kyrion.core.integration

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.activity.*
import dev.kyrion.core.home.RoomRepository
import dev.kyrion.core.security.workspaceOwnerId
import dev.kyrion.core.security.authenticatedUserId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import org.springframework.stereotype.Service
import org.springframework.transaction.support.TransactionTemplate
import org.springframework.web.bind.annotation.*
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.util.UUID

data class HomeAssistantSelectedDevice(
    val externalId: String, val entities: Set<String>, val control: Boolean,
    val roomOverride: Boolean, val roomId: UUID?,
)
data class HomeAssistantSelection(val revision: Long, val devices: List<HomeAssistantSelectedDevice>) {
    fun entityMap() = devices.associate { it.externalId to it.entities }
}

@Repository
class HomeAssistantSelectionStore(private val jdbc: JdbcClient) {
    private val mapper = jacksonObjectMapper()
    fun load(ownerId: UUID): HomeAssistantSelection? {
        val revision = jdbc.sql("SELECT revision FROM home_assistant_selection_state WHERE owner_id=:owner")
            .param("owner", ownerId).query(Long::class.java).optional().orElse(null) ?: return null
        val devices = jdbc.sql("SELECT * FROM home_assistant_device_selection WHERE owner_id=:owner ORDER BY external_id")
            .param("owner", ownerId).query { rs, _ ->
                val rows = mapper.readTree(rs.getString("entity_ids"))
                check(rows.isArray && rows.size() in 1..2000 && rows.all { it.isTextual })
                HomeAssistantSelectedDevice(rs.getString("external_id"), rows.map { it.asText() }.toSet(),
                    rs.getBoolean("control_enabled"), rs.getBoolean("room_override"), rs.getObject("room_id", UUID::class.java))
            }.list()
        return HomeAssistantSelection(revision, devices)
    }

    /** Caller holds the existing owner row lock in a transaction. */
    fun replace(ownerId: UUID, expectedRevision: Long, devices: List<HomeAssistantSelectedDevice>): Long {
        val current = load(ownerId)?.revision ?: 0L
        if (expectedRevision != current) throw HomeAssistantException("selection_conflict")
        jdbc.sql("DELETE FROM home_assistant_device_selection WHERE owner_id=:owner").param("owner", ownerId).update()
        devices.forEach { device ->
            jdbc.sql("""INSERT INTO home_assistant_device_selection(owner_id,external_id,entity_ids,control_enabled,room_override,room_id)
                VALUES(:owner,:external,:entities,:control,:override,:room)""")
                .param("owner", ownerId).param("external", device.externalId)
                .param("entities", mapper.writeValueAsString(device.entities.sorted())).param("control", device.control)
                .param("override", device.roomOverride).param("room", device.roomId, java.sql.Types.OTHER).update()
        }
        jdbc.sql("""INSERT INTO home_assistant_selection_state(owner_id,revision,updated_at) VALUES(:owner,:revision,CURRENT_TIMESTAMP)
            ON CONFLICT(owner_id) DO UPDATE SET revision=EXCLUDED.revision,updated_at=EXCLUDED.updated_at""")
            .param("owner", ownerId).param("revision", current + 1).update()
        return current + 1
    }
}

data class HomeAssistantEntityPreview(val key: String, val name: String, val state: String, val supportsPower: Boolean)
data class HomeAssistantDevicePreview(val key: String, val name: String, val sourceRoom: String?, val entities: List<HomeAssistantEntityPreview>)
data class HomeAssistantPreview(val revision: Long, val devices: List<HomeAssistantDevicePreview>)
data class HomeAssistantDeviceChoice(
    val key: String, val entityKeys: List<String>, val allowControl: Boolean = false,
    val overrideRoom: Boolean = false, val roomId: UUID? = null,
)
class HomeAssistantOnboardRequest(
    val baseUrl: String? = null, val accessToken: String? = null, val expectedRevision: Long, val devices: List<HomeAssistantDeviceChoice>,
) {
    override fun toString() = "HomeAssistantOnboardRequest(accessToken=<redacted>)"
}
data class HomeAssistantSelectionResult(val revision: Long, val selected: Int, val imported: Int, val reason: String?, val correlationId: UUID)
data class HomeAssistantSelectionView(val revision: Long, val devices: List<HomeAssistantDeviceChoice>)

internal fun haSourceKey(ownerId: UUID, config: HomeAssistantConnectionConfig, externalId: String, entityId: String? = null): String {
    val value = listOf(ownerId.toString(), config.baseUrl.trimEnd('/'), externalId, entityId.orEmpty()).joinToString("\u001f")
    return MessageDigest.getInstance("SHA-256").digest(value.toByteArray(StandardCharsets.UTF_8)).joinToString("") { "%02x".format(it) }
}

internal fun resolveHaChoices(ownerId: UUID, config: HomeAssistantConnectionConfig, inventory: List<HomeAssistantDevice>,
                              choices: List<HomeAssistantDeviceChoice>, roomIds: Set<UUID>): List<HomeAssistantSelectedDevice> {
    if (choices.size > 250 || choices.map { it.key }.distinct().size != choices.size || choices.sumOf { it.entityKeys.size } > 2000) {
        throw HomeAssistantException("selection_invalid")
    }
    val byKey = inventory.associateBy { haSourceKey(ownerId, config, it.externalId) }
    return choices.map { choice ->
        val device = byKey[choice.key] ?: throw HomeAssistantException("selection_invalid")
        if (choice.entityKeys.isEmpty() || choice.entityKeys.distinct().size != choice.entityKeys.size ||
            choice.roomId != null && (!choice.overrideRoom || choice.roomId !in roomIds)) throw HomeAssistantException("selection_invalid")
        val entities = device.entities.associateBy { haSourceKey(ownerId, config, device.externalId, it.id) }
        val selected = choice.entityKeys.map { entities[it] ?: throw HomeAssistantException("selection_invalid") }
        if (choice.allowControl && selected.count { it.supportsPower } != 1) throw HomeAssistantException("control_unsupported")
        HomeAssistantSelectedDevice(device.externalId, selected.map { it.id }.toSet(), choice.allowControl, choice.overrideRoom, choice.roomId)
    }
}

@Service
class HomeAssistantSelectionService(
    private val store: HomeAssistantSelectionStore, private val client: HomeAssistantClient,
    private val connections: HomeAssistantConnectionStore, private val rooms: RoomRepository,
    private val importer: HomeAssistantImportService, private val jdbc: JdbcClient,
    private val transactions: TransactionTemplate, private val activity: ActivityService,
) {
    fun previewStored(ownerId: UUID) = preview(ownerId, connections.findForOwner(ownerId) ?: throw HomeAssistantException("configuration_missing"))
    fun selected(ownerId: UUID): Pair<Long, List<HomeAssistantDeviceChoice>> {
        val selection = store.load(ownerId) ?: return 0L to emptyList()
        val config = connections.findForOwner(ownerId) ?: throw HomeAssistantException("configuration_missing")
        return selection.revision to selection.devices.map { device ->
            HomeAssistantDeviceChoice(haSourceKey(ownerId, config, device.externalId), device.entities.sorted().map { haSourceKey(ownerId, config, device.externalId, it) },
                device.control, device.roomOverride, device.roomId)
        }
    }
    fun preview(ownerId: UUID, config: HomeAssistantConnectionConfig): HomeAssistantPreview {
        val inventory = client.snapshot(config)
        return HomeAssistantPreview(store.load(ownerId)?.revision ?: 0, inventory.map { device ->
            HomeAssistantDevicePreview(haSourceKey(ownerId, config, device.externalId), device.name, device.area,
                device.entities.map { entity -> HomeAssistantEntityPreview(haSourceKey(ownerId, config, device.externalId, entity.id),
                    entity.name, entity.state, entity.supportsPower) })
        })
    }

    fun configure(ownerId: UUID, request: HomeAssistantOnboardRequest, actorId: UUID = ownerId): HomeAssistantSelectionResult {
        if (request.expectedRevision < 0 || request.devices.size > 250) throw HomeAssistantException("selection_invalid")
        val initial = connections.findForOwner(ownerId)
        val useStored = request.accessToken.isNullOrEmpty()
        val config = if (useStored) {
            initial?.takeIf { request.baseUrl.isNullOrEmpty() || request.baseUrl.trimEnd('/') == it.baseUrl.trimEnd('/') }
                ?: throw HomeAssistantException("configuration_missing")
        } else HomeAssistantConnectionConfig(request.baseUrl.orEmpty(), request.accessToken.orEmpty())
        val inventory = client.snapshot(config)
        val selected = resolveHaChoices(ownerId, config, inventory, request.devices, rooms.all(ownerId).map { it.id }.toSet())
        val correlation = UUID.randomUUID()
        val revision = transactions.execute {
            jdbc.sql("SELECT id FROM user_account WHERE id=:owner FOR UPDATE").param("owner", ownerId).query(UUID::class.java).single()
            val existing = connections.findForOwner(ownerId)
            if (existing != null && existing.baseUrl.trimEnd('/') != config.baseUrl.trimEnd('/')) throw HomeAssistantException("connection_change_requires_disconnect")
            if (useStored && (existing == null || existing.accessToken != config.accessToken)) throw HomeAssistantException("selection_conflict")
            if (!useStored) connections.saveForOwner(ownerId, config)
            val saved = store.replace(ownerId, request.expectedRevision, selected)
            activity.record(ActivityCategory.INTEGRATION, "integration.home_assistant.selection.updated", ActivityStatus.SUCCEEDED,
                ActivityActorType.USER, "home_assistant", "selection.updated", actorId.toString(), correlation, ownerId)
            saved
        } ?: throw HomeAssistantException("internal_error")
        val result = importer.sync(ownerId)
        return HomeAssistantSelectionResult(revision, selected.size, result.imported, result.reason, result.correlationId)
    }
}

@RestController
@RequestMapping("/v1/integrations/home-assistant")
class HomeAssistantSelectionController(private val service: HomeAssistantSelectionService) {
    @GetMapping("/preview")
    fun previewStored(request: HttpServletRequest) = service.previewStored(request.workspaceOwnerId())

    @GetMapping("/selection")
    fun selected(request: HttpServletRequest): HomeAssistantSelectionView {
        val (revision, devices) = service.selected(request.workspaceOwnerId())
        return HomeAssistantSelectionView(revision, devices)
    }
    @PostMapping("/preview")
    fun preview(@RequestBody body: HomeAssistantConnectionRequest, request: HttpServletRequest) =
        service.preview(request.workspaceOwnerId(), HomeAssistantConnectionConfig(body.baseUrl, body.accessToken))

    @PostMapping("/selection")
    fun configure(@RequestBody body: HomeAssistantOnboardRequest, request: HttpServletRequest) = service.configure(request.workspaceOwnerId(), body, request.authenticatedUserId())

    @ExceptionHandler(HomeAssistantException::class)
    fun error(exception: HomeAssistantException) = org.springframework.http.ResponseEntity.status(409).body(mapOf("code" to exception.code))
}
