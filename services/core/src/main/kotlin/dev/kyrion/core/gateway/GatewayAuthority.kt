package dev.kyrion.core.gateway

import dev.kyrion.core.action.ActionContext
import dev.kyrion.core.action.InteractionChannel
import dev.kyrion.core.activity.ActivityActorType
import dev.kyrion.core.security.ForbiddenException
import dev.kyrion.core.security.RbacService
import dev.kyrion.core.security.TenantBoundary
import dev.kyrion.core.security.authenticatedUserId
import dev.kyrion.core.security.workspaceOwnerId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Service
import java.time.Clock
import java.sql.Timestamp
import java.util.UUID

enum class GatewayPrincipalKind { HUMAN, AUTOMATION, HOME_VOICE }

/** Server-created provenance. Never accepted as an HTTP body or gateway payload. */
data class GatewayAuthority(
    val spaceId: UUID,
    val kind: GatewayPrincipalKind,
    val principalId: UUID,
    val permission: String,
    val capability: String,
    val grantId: UUID? = null,
    val sessionId: UUID? = null,
    val sourceNodeId: UUID? = null,
    val targetId: UUID? = null,
) {
    companion object {
        fun human(request: HttpServletRequest, permission: String, capability: String) = GatewayAuthority(
            request.workspaceOwnerId(), GatewayPrincipalKind.HUMAN, request.authenticatedUserId(), permission, capability,
        )

        fun action(context: ActionContext, capability: String): GatewayAuthority {
            val principal = context.actorId?.let { runCatching { UUID.fromString(it) }.getOrNull() }
                ?: throw ForbiddenException()
            val kind = when {
                context.actorType == ActivityActorType.USER -> GatewayPrincipalKind.HUMAN
                context.actorType == ActivityActorType.INTEGRATION && context.channel == InteractionChannel.VOICE -> GatewayPrincipalKind.HOME_VOICE
                context.actorType == ActivityActorType.INTEGRATION && context.channel == InteractionChannel.AUTOMATION -> GatewayPrincipalKind.AUTOMATION
                else -> throw ForbiddenException()
            }
            return GatewayAuthority(context.ownerId, kind, principal, "devices:execute", capability,
                context.automationGrantId, context.sessionId, context.automationNodeId)
        }
    }
}

@Service
class GatewayAuthorityService(
    private val boundary: TenantBoundary,
    private val rbac: RbacService,
    private val jdbc: JdbcClient,
    private val clock: Clock = Clock.systemUTC(),
    private val nodes: GatewayRepository,
    private val catalog: dev.kyrion.core.capability.DeviceCatalogService,
) {
    fun bindTarget(authority: GatewayAuthority, type: String, payload: Map<String, Any>): GatewayAuthority {
        if (type !in DEVICE_TYPES) return authority
        val target = jdbc.sql("SELECT id FROM integration_connection WHERE owner_id=:space AND provider=:provider AND endpoint_host=:address")
            .param("space", authority.spaceId).param("provider", type.substringBefore('.')).param("address", payload["deviceId"])
            .query(UUID::class.java).optional().orElse(null) ?: throw ForbiddenException()
        return authority.copy(targetId = target)
    }

    fun validateTarget(authority: GatewayAuthority, targetId: UUID, on: Boolean?) {
        validate(authority, null, null)
        if (authority.kind != GatewayPrincipalKind.AUTOMATION) return
        if (!jdbc.sql("""SELECT EXISTS(SELECT 1 FROM zigbee_button_binding b JOIN integration_connection c
            ON c.owner_id=b.owner_id AND (c.id=b.target_connection_id OR c.room_id=b.target_room_id)
            WHERE b.grant_id=:grant AND b.owner_id=:space AND c.id=:target
            AND (b.action='toggle' OR (b.action='turn_on' AND :on=true) OR (b.action='turn_off' AND :on=false)))""")
            .param("grant", authority.grantId).param("space", authority.spaceId).param("target", targetId).param("on", on)
            .query(Boolean::class.java).single()) throw ForbiddenException()
    }

    fun validate(authority: GatewayAuthority, nodeId: UUID?, type: String?, payload: Map<String, Any> = emptyMap()) {
        boundary.workspace(authority.spaceId)
        if (type != null && authority.capability != capability(type)) throw ForbiddenException()
        if (nodeId != null && !exists("SELECT EXISTS(SELECT 1 FROM gateway_node WHERE id=:node AND owner_id=:space)", authority, nodeId)) throw ForbiddenException()
        if (nodeId != null && type in DEVICE_TYPES) {
            val address = payload["deviceId"] as? String ?: throw ForbiddenException()
            val provider = type!!.substringBefore('.')
            if (authority.targetId == null || !jdbc.sql("""SELECT EXISTS(SELECT 1 FROM integration_connection
                WHERE id=:target AND owner_id=:space AND endpoint_host=:address AND provider=:provider)""")
                .param("target", authority.targetId).param("space", authority.spaceId).param("address", address)
                .param("provider", provider).query(Boolean::class.java).single()) throw ForbiddenException()
            val health = nodes.findById(nodeId)?.health ?: throw ForbiddenException()
            val observed = if (provider == "zigbee") health.zigbee?.devices?.any { it.ieeeAddress == address } == true
                else health.bluetoothDevices.any { it.address == address }
            if (!observed) throw ForbiddenException()
            if (authority.capability in ROUTINE && catalog.devices(authority.spaceId)
                    .singleOrNull { it.id == authority.targetId }?.capabilities?.none { it.id == authority.capability } != false) {
                throw ForbiddenException()
            }
        }
        when (authority.kind) {
            GatewayPrincipalKind.HUMAN -> {
                boundary.shared(authority.principalId, authority.spaceId)
                rbac.require(authority.principalId, authority.permission)
                if (authority.permission !in permissions(type)) throw ForbiddenException()
            }
            GatewayPrincipalKind.HOME_VOICE -> {
                boundary.voice(authority.spaceId)
                if (authority.permission != "devices:execute" || authority.capability !in ROUTINE || authority.sessionId == null ||
                    !exists("""SELECT EXISTS(SELECT 1 FROM voice_dialogue_session s JOIN voice_satellite v
                        ON v.id=s.satellite_id AND v.owner_id=s.owner_id WHERE s.id=:session
                        AND s.satellite_id=:principal AND s.owner_id=:space AND s.status='active' AND s.expires_at>:now)""", authority)) throw ForbiddenException()
            }
            GatewayPrincipalKind.AUTOMATION -> validateGrant(authority, nodeId, payload)
        }
    }

    private fun validateGrant(authority: GatewayAuthority, nodeId: UUID?, payload: Map<String, Any>) {
        if (authority.permission != "devices:execute" || authority.capability != "power.set" || authority.grantId == null) throw ForbiddenException()
        val grants = jdbc.sql("""SELECT b.granted_by,b.source_node_id,b.target_connection_id,b.target_room_id,b.action
            FROM zigbee_button_binding b JOIN integration_connection c ON c.id=b.button_connection_id AND c.owner_id=b.owner_id
            JOIN gateway_node n ON n.id=b.source_node_id AND n.owner_id=b.owner_id
            WHERE b.grant_id=:grant AND b.owner_id=:space AND b.button_connection_id=:principal AND c.provider='zigbee'""")
            .param("grant", authority.grantId).param("space", authority.spaceId).param("principal", authority.principalId)
            .query { rs, _ -> Grant(rs.getObject(1, UUID::class.java), rs.getObject(2, UUID::class.java),
                rs.getObject(3, UUID::class.java), rs.getObject(4, UUID::class.java), rs.getString(5)) }.list()
        val grant = grants.singleOrNull() ?: throw ForbiddenException()
        val button = jdbc.sql("SELECT endpoint_host FROM integration_connection WHERE id=:button AND owner_id=:space")
            .param("button", authority.principalId).param("space", authority.spaceId).query(String::class.java).single()
        if (nodes.findById(grant.sourceNode)?.health?.zigbee?.devices?.none { it.ieeeAddress == button } != false) throw ForbiddenException()
        if (authority.sourceNodeId != grant.sourceNode) throw ForbiddenException()
        boundary.shared(grant.actor, authority.spaceId)
        rbac.require(grant.actor, "devices:update")
        rbac.require(grant.actor, "devices:execute")
        if (nodeId != null) {
            // The target may be on another node in the same Space; bind it to that
            // node's current device observation below, never to a foreign node.
            val address = payload["deviceId"] as? String ?: throw ForbiddenException()
            val allowed = jdbc.sql("""SELECT EXISTS(SELECT 1 FROM integration_connection c WHERE c.owner_id=:space
                AND c.id=:commandTarget AND c.endpoint_host=:address AND c.provider IN ('zigbee','bluetooth')
                AND ((CAST(:target AS uuid) IS NOT NULL AND c.id=:target) OR (CAST(:room AS uuid) IS NOT NULL AND c.room_id=:room)))""")
                .param("space", authority.spaceId).param("commandTarget", authority.targetId).param("address", address).param("target", grant.target)
                .param("room", grant.room).query(Boolean::class.java).single()
            if (!allowed || (grant.action == "turn_on" && payload["on"] != true) ||
                (grant.action == "turn_off" && payload["on"] != false)) throw ForbiddenException()
        }
    }

    private data class Grant(val actor: UUID, val sourceNode: UUID, val target: UUID?, val room: UUID?, val action: String)

    private fun exists(sql: String, authority: GatewayAuthority, nodeId: UUID? = null): Boolean {
        val query = jdbc.sql(sql).param("space", authority.spaceId)
        if (sql.contains(":node")) query.param("node", nodeId)
        if (sql.contains(":principal")) query.param("principal", authority.principalId)
        if (sql.contains(":session")) query.param("session", authority.sessionId)
        if (sql.contains(":now")) query.param("now", Timestamp.from(clock.instant()))
        return query.query(Boolean::class.java).single()
    }

    companion object {
        private val DEVICE_TYPES = setOf("zigbee.power", "zigbee.brightness", "zigbee.color", "bluetooth.power", "bluetooth.brightness", "bluetooth.color", "zigbee.remove", "zigbee.hue_power_on_recover")
        val ROUTINE = setOf("power.set", "light.setBrightness", "light.setColour")
        fun capability(type: String): String = when (type) {
            "zigbee.power", "bluetooth.power" -> "power.set"
            "zigbee.brightness", "bluetooth.brightness" -> "light.setBrightness"
            "zigbee.color", "bluetooth.color" -> "light.setColour"
            "zigbee.permit_join", "zigbee.remove", "zigbee.hue_power_on_recover", "youtube.play" -> type
            else -> throw GatewayCommandInvalidException()
        }
        private fun permissions(type: String?): Set<String> = when (type) {
            null -> setOf("devices:execute")
            "zigbee.remove" -> setOf("integrations:delete")
            "youtube.play" -> setOf("integrations:create")
            "zigbee.permit_join", "zigbee.hue_power_on_recover" -> setOf("gateways:execute")
            else -> setOf("devices:execute", "gateways:execute")
        }
    }
}
