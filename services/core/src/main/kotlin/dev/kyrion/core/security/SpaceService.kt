package dev.kyrion.core.security

import dev.kyrion.core.activity.*
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.Size
import org.springframework.boot.ApplicationArguments
import org.springframework.boot.ApplicationRunner
import org.springframework.http.HttpStatus
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Component
import org.springframework.stereotype.Service
import org.springframework.transaction.annotation.Transactional
import org.springframework.web.bind.annotation.*
import java.sql.Timestamp
import java.time.Clock
import java.time.Instant
import java.util.UUID

enum class SpaceType { HOME, BUSINESS }
data class SpaceView(val id: UUID, val type: SpaceType, val name: String, val status: String, val defaultRoleKey: String)
data class SpaceSettingsRequest(
    @field:Size(min = 1, max = 120) val name: String,
    val type: SpaceType,
    @field:Size(min = 1, max = 80) val defaultRoleKey: String = "USER",
)
data class InvitationOptions(val roleId: UUID? = null, val expiresInHours: Int? = null, val maxUses: Int? = null)
data class SpaceInvitationView(
    val id: UUID, val createdBy: UUID, val createdAt: Instant, val expiresAt: Instant,
    val roleKey: String, val maxUses: Int, val useCount: Int, val status: String,
)
data class IssuedSpaceInvitation(val id: UUID, val code: String, val expiresAt: Instant, val roleKey: String, val maxUses: Int)
class InvalidSpaceSettingsException : RuntimeException()

/** No client-supplied Space identifier participates in authorization. */
@Service
class SpaceService(
    private val jdbc: JdbcClient,
    private val rbac: RbacService,
    private val activity: ActivityService,
    private val clock: Clock = Clock.systemUTC(),
    private val creationLimiter: InvitationCreationLimiter = InvitationCreationLimiter(clock),
) {
    fun current(actor: UUID): SpaceView = jdbc.sql(
        """SELECT s.* FROM kyrion_space s JOIN user_account u ON u.space_id=s.id
           WHERE u.id=:actor AND u.enabled AND s.status='ACTIVE'""",
    ).param("actor", actor).query { rs, _ ->
        SpaceView(rs.getObject("id", UUID::class.java), SpaceType.valueOf(rs.getString("type")),
            rs.getString("name"), rs.getString("status"), rs.getString("default_role_key"))
    }.optional().orElseThrow { ForbiddenException() }

    @Transactional
    fun update(actor: UUID, request: SpaceSettingsRequest): SpaceView {
        val owner = rbac.lockIdentity(actor)
        if (!rbac.isOwner(actor)) throw ForbiddenException()
        val name = request.name.trim()
        if (name.isEmpty() || name.length > 120 || name.any { it.isISOControl() } || request.defaultRoleKey == "OWNER")
            throw InvalidSpaceSettingsException()
        if (rbac.roles(owner).none { it.key == request.defaultRoleKey && it.key != "OWNER" }) throw RoleNotFoundException()
        jdbc.sql("UPDATE kyrion_space SET name=:name,type=:type,default_role_key=:role,updated_at=CURRENT_TIMESTAMP WHERE id=:owner AND status='ACTIVE'")
            .param("name", name).param("type", request.type.name).param("role", request.defaultRoleKey).param("owner", owner).update()
        audit("space.settings.updated", actor, owner)
        return current(actor)
    }

    @Transactional
    fun createInvitation(actor: UUID, options: InvitationOptions): IssuedSpaceInvitation {
        val owner = rbac.authorizeMutation(actor, "invitations:create")
        val space = current(actor)
        val hours = options.expiresInHours ?: 24
        val uses = options.maxUses ?: 1
        if (hours !in 1..168 || uses !in 1..20) throw InvalidSpaceSettingsException()
        val role = rbac.roles(owner).firstOrNull {
            if (options.roleId == null) it.key == space.defaultRoleKey else it.id == options.roleId
        } ?: throw RoleNotFoundException()
        if (role.key == "OWNER" || !rbac.permissions(actor).containsAll(role.permissions)) throw ForbiddenException()
        creationLimiter.check(actor)
        // Serialize issuance with role edits; redemption revalidates the grant as well.
        val token = SessionTokenService().create()
        val id = UUID.randomUUID()
        val expiry = clock.instant().plusSeconds(hours * 3600L)
        jdbc.sql("""INSERT INTO registration_invitation(id,token_hash,created_by,workspace_owner_id,expires_at,role_id,max_uses)
                    VALUES(:id,:hash,:actor,:owner,:expires,:role,:uses)""")
            .param("id", id).param("hash", token.tokenHash).param("actor", actor).param("owner", owner)
            .param("expires", Timestamp.from(expiry)).param("role", role.id).param("uses", uses).update()
        audit("space.invitation.created", actor, id)
        return IssuedSpaceInvitation(id, token.rawToken, expiry, role.key, uses)
    }

    fun invitations(actor: UUID): List<SpaceInvitationView> {
        rbac.require(actor, "invitations:create")
        val owner = current(actor).id
        return jdbc.sql("""SELECT i.*, COALESCE(r.role_key,s.default_role_key) AS assigned_role
            FROM registration_invitation i JOIN kyrion_space s ON s.id=i.workspace_owner_id
            LEFT JOIN rbac_role r ON r.id=i.role_id WHERE i.workspace_owner_id=:owner ORDER BY i.created_at DESC LIMIT 200""")
            .param("owner", owner).query { rs, _ ->
                val expiry = rs.getTimestamp("expires_at").toInstant()
                val used = rs.getInt("use_count")
                val max = rs.getInt("max_uses")
                val status = when {
                    rs.getTimestamp("revoked_at") != null -> "REVOKED"
                    used >= max || rs.getTimestamp("redeemed_at") != null -> "USED"
                    !expiry.isAfter(clock.instant()) -> "EXPIRED"
                    else -> "ACTIVE"
                }
                SpaceInvitationView(rs.getObject("id", UUID::class.java), rs.getObject("created_by", UUID::class.java),
                    rs.getTimestamp("created_at").toInstant(), expiry, rs.getString("assigned_role"), max, used, status)
            }.list()
    }

    @Transactional
    fun revoke(actor: UUID, id: UUID) {
        val owner = rbac.authorizeMutation(actor, "invitations:create")
        current(actor)
        val updated = jdbc.sql("UPDATE registration_invitation SET revoked_at=COALESCE(revoked_at,:now) WHERE id=:id AND workspace_owner_id=:owner")
            .param("now", Timestamp.from(clock.instant())).param("id", id).param("owner", owner).update()
        if (updated != 1) throw InvalidInvitationException()
        audit("space.invitation.revoked", actor, id)
    }

    private fun audit(type: String, actor: UUID, target: UUID) = activity.record(
        ActivityCategory.SECURITY, type, ActivityStatus.SUCCEEDED, ActivityActorType.USER,
        "kyrion-core", target.toString(), actor.toString(), ownerId = rbac.workspace(actor),
    )
}

/** Bound authenticated invitation issuance without persisting raw credentials. */
@Component
class InvitationCreationLimiter(private val clock: Clock = Clock.systemUTC()) {
    private data class Window(val startedAt: Instant, val count: Int)
    private val windows = LinkedHashMap<UUID, Window>()

    @Synchronized
    fun check(actor: UUID) {
        val now = clock.instant()
        val previous = windows[actor]?.takeIf { now.isBefore(it.startedAt.plusSeconds(60)) }
        if (previous != null && previous.count >= 20) {
            throw LoginRateLimitedException(java.time.Duration.between(now, previous.startedAt.plusSeconds(60)))
        }
        windows[actor] = Window(previous?.startedAt ?: now, (previous?.count ?: 0) + 1)
        while (windows.size > 10_000) windows.remove(windows.keys.first())
    }
}

/** Global discovery/worker state has not been certified for multiple Spaces. */
@Component
class SingleSpaceRuntimeGuard(private val jdbc: JdbcClient) : ApplicationRunner {
    override fun run(args: ApplicationArguments) {
        check(jdbc.sql("SELECT count(*) FROM kyrion_space").query(Long::class.java).single() <= 1) {
            "MULTI_SPACE_RUNTIME_UNSUPPORTED: run each Space in a separate installation until worker isolation is implemented"
        }
    }
}

@RestController
@RequestMapping("/v1/space")
class SpaceController(private val spaces: SpaceService) {
    @GetMapping fun current(request: HttpServletRequest) = spaces.current(request.authenticatedUserId())
    @PutMapping fun update(@Valid @RequestBody body: SpaceSettingsRequest, request: HttpServletRequest) = spaces.update(request.authenticatedUserId(), body)
    @GetMapping("/invitations") fun invitations(request: HttpServletRequest) = spaces.invitations(request.authenticatedUserId())
    @PostMapping("/invitations") @ResponseStatus(HttpStatus.CREATED)
    fun invite(@RequestBody body: InvitationOptions, request: HttpServletRequest) = spaces.createInvitation(request.authenticatedUserId(), body)
    @DeleteMapping("/invitations/{id}") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun revoke(@PathVariable id: UUID, request: HttpServletRequest) = spaces.revoke(request.authenticatedUserId(), id)
}

@RestControllerAdvice
class SpaceErrorHandler {
    @ExceptionHandler(InvalidSpaceSettingsException::class) @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = ErrorResponse("SPACE_SETTINGS_INVALID")
}
