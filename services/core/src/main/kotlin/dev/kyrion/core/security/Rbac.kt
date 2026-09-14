package dev.kyrion.core.security

import dev.kyrion.core.activity.*
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import org.springframework.http.HttpStatus
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.*
import java.time.Clock
import java.time.Instant
import java.util.UUID

enum class PermissionOperation { CREATE, READ, UPDATE, DELETE, EXECUTE }
data class PermissionDefinition(val key: String, val resource: String, val operation: PermissionOperation)
data class RoleView(val id: UUID, val key: String, val name: String, val system: Boolean, val permissions: Set<String>, val userCount: Int)
data class UserView(val id: UUID, val username: String, val enabled: Boolean, val roles: List<String>, val permissions: Set<String>)
data class RoleRequest(@field:NotBlank val key: String, @field:NotBlank val name: String, val permissions: Set<String> = emptySet())
data class RoleAssignmentRequest(val roleIds: Set<UUID>)

class ForbiddenException : RuntimeException()
class RoleNotFoundException : RuntimeException()
class PermissionNotFoundException : RuntimeException()
class RoleInUseException : RuntimeException()
class LastOwnerProtectedException : RuntimeException()
class SystemRoleProtectedException : RuntimeException()
class UserDisabledException : RuntimeException()

@Service
class RbacService(private val jdbc: JdbcClient, private val activity: ActivityService, private val clock: Clock = Clock.systemUTC()) {
    fun initializeUser(userId: UUID, ownerId: UUID, owner: Boolean) {
        ensureRoles(ownerId)
        val key = if (owner) "OWNER" else "USER"
        jdbc.sql("INSERT INTO rbac_user_role(user_id, role_id) SELECT :user, id FROM rbac_role WHERE installation_owner_id=:owner AND role_key=:key ON CONFLICT DO NOTHING")
            .param("user", userId).param("owner", ownerId).param("key", key).update()
    }
    private fun ensureRoles(ownerId: UUID) {
        listOf("OWNER", "ADMIN", "USER", "VIEWER").forEach { key ->
            jdbc.sql("INSERT INTO rbac_role(id, installation_owner_id, role_key, display_name, system_role) VALUES (:id,:owner,:key,:key,TRUE) ON CONFLICT DO NOTHING")
                .param("id", UUID.randomUUID()).param("owner", ownerId).param("key", key).update()
        }
        jdbc.sql("INSERT INTO rbac_role_permission(role_id, permission_key) SELECT r.id,p.permission_key FROM rbac_role r CROSS JOIN rbac_permission p WHERE r.installation_owner_id=:owner AND r.role_key='OWNER' ON CONFLICT DO NOTHING").param("owner", ownerId).update()
        jdbc.sql("INSERT INTO rbac_role_permission(role_id, permission_key) SELECT r.id,p.permission_key FROM rbac_role r JOIN rbac_permission p ON p.operation='READ' AND p.resource NOT IN ('users','roles','permissions','invitations','backups','system_settings','activity_log') WHERE r.installation_owner_id=:owner AND r.role_key='VIEWER' ON CONFLICT DO NOTHING").param("owner", ownerId).update()
        val adminExcluded = "users:read,users:create,users:update,users:delete,roles:read,roles:create,roles:update,roles:delete,permissions:read,invitations:create,rooms:read,rooms:create,rooms:update,rooms:delete,devices:read,devices:create,devices:update,devices:delete,devices:execute,integrations:read,integrations:create,integrations:update,integrations:delete,integrations:execute,gateways:read,gateways:create,gateways:update,gateways:delete,gateways:execute,voice_satellites:read,voice_satellites:create,voice_satellites:update,voice_satellites:delete,voice_satellites:execute,automations:read,automations:create,automations:update,automations:delete,automations:execute,activity_log:read,backups:read,backups:create,backups:delete,system_settings:read,system_settings:update".split(',')
        adminExcluded.forEach { key -> jdbc.sql("INSERT INTO rbac_role_permission(role_id,permission_key) SELECT id,:key FROM rbac_role WHERE installation_owner_id=:owner AND role_key='ADMIN' ON CONFLICT DO NOTHING").param("key",key).param("owner",ownerId).update() }
        "rooms:read,rooms:create,rooms:update,rooms:delete,devices:read,devices:execute,automations:read,automations:create,automations:update,automations:delete,automations:execute,conversations:read,conversations:create,conversations:update,conversations:delete,personal_memories:read,personal_memories:create,personal_memories:update,personal_memories:delete,integrations:read,integrations:execute".split(',').forEach { key -> jdbc.sql("INSERT INTO rbac_role_permission(role_id,permission_key) SELECT id,:key FROM rbac_role WHERE installation_owner_id=:owner AND role_key='USER' ON CONFLICT DO NOTHING").param("key",key).param("owner",ownerId).update() }
    }
    fun permissions(userId: UUID): Set<String> = jdbc.sql("SELECT DISTINCT rp.permission_key FROM rbac_user_role ur JOIN rbac_role_permission rp ON rp.role_id=ur.role_id JOIN rbac_role r ON r.id=ur.role_id WHERE ur.user_id=:id AND r.role_key<>'OWNER'").param("id", userId).query(String::class.java).list().mapNotNull { it }.toSet().let { keys -> if (isOwner(userId)) permissionCatalog().map { it.key }.toSet() else keys }
    fun isOwner(userId: UUID) = jdbc.sql("SELECT EXISTS(SELECT 1 FROM user_account u LEFT JOIN rbac_user_role ur ON ur.user_id=u.id LEFT JOIN rbac_role r ON r.id=ur.role_id AND r.role_key='OWNER' WHERE u.id=:id AND (r.role_key='OWNER' OR u.workspace_owner_id IS NULL))").param("id", userId).query(Boolean::class.java).single()
    fun require(userId: UUID, permission: String) { if (permission !in permissionCatalog().map { it.key } || permission !in permissions(userId)) throw ForbiddenException() }
    fun permissionCatalog(): List<PermissionDefinition> = jdbc.sql("SELECT permission_key, resource, operation FROM rbac_permission ORDER BY resource, operation").query { rs, _ -> PermissionDefinition(rs.getString(1), rs.getString(2), PermissionOperation.valueOf(rs.getString(3))) }.list()
    fun roles(ownerId: UUID): List<RoleView> = jdbc.sql("SELECT id, role_key, display_name, system_role FROM rbac_role WHERE installation_owner_id=:owner ORDER BY system_role DESC, role_key").param("owner", ownerId).query { rs, _ -> role(rs.getObject(1, UUID::class.java), rs.getString(2), rs.getString(3), rs.getBoolean(4), ownerId) }.list()
    fun users(ownerId: UUID): List<UserView> = jdbc.sql("SELECT id, username, enabled FROM user_account WHERE id=:owner OR workspace_owner_id=:owner ORDER BY username").param("owner", ownerId).query { rs, _ -> user(rs.getObject(1, UUID::class.java), rs.getString(2), rs.getBoolean(3)) }.list()
    fun createRole(ownerId: UUID, request: RoleRequest): RoleView { validatePermissions(request.permissions); val id=UUID.randomUUID(); jdbc.sql("INSERT INTO rbac_role(id,installation_owner_id,role_key,display_name) VALUES (:id,:owner,:key,:name)").param("id",id).param("owner",ownerId).param("key",request.key.trim().lowercase()).param("name",request.name.trim()).update(); setPermissions(ownerId,id,request.permissions); audit("rbac.role.created",ownerId); return roles(ownerId).first { it.id==id } }
    fun updateRole(ownerId: UUID, id: UUID, request: RoleRequest): RoleView { val existing = roleRow(ownerId,id); if(existing.system) throw SystemRoleProtectedException(); validatePermissions(request.permissions); jdbc.sql("UPDATE rbac_role SET role_key=:key, display_name=:name, updated_at=:now WHERE id=:id AND installation_owner_id=:owner").param("key",request.key.trim().lowercase()).param("name",request.name.trim()).param("now",clock.instant()).param("id",id).param("owner",ownerId).update(); setPermissions(ownerId,id,request.permissions); audit("rbac.role.updated",ownerId); return roles(ownerId).first { it.id==id } }
    fun deleteRole(ownerId: UUID,id:UUID) { val r=roleRow(ownerId,id); if(r.system) throw SystemRoleProtectedException(); if(jdbc.sql("SELECT COUNT(*) FROM rbac_user_role WHERE role_id=:id").param("id",id).query(Int::class.java).single()>0) throw RoleInUseException(); jdbc.sql("DELETE FROM rbac_role WHERE id=:id AND installation_owner_id=:owner").param("id",id).param("owner",ownerId).update(); audit("rbac.role.deleted",ownerId) }
    fun assignRoles(actor: UUID, userId: UUID, ids: Set<UUID>) { require(actor,"users:update"); val target=jdbc.sql("SELECT id FROM user_account WHERE id=:id AND (id=:owner OR workspace_owner_id=:owner)").param("id",userId).param("owner",workspace(actor)).query(UUID::class.java).optional().orElseThrow{RoleNotFoundException()}; if(ids.isEmpty() || (isOwner(userId) && ids.none { roleKey(it)=="OWNER" })) throw LastOwnerProtectedException(); ids.forEach { roleRow(workspace(actor),it) }; jdbc.sql("DELETE FROM rbac_user_role WHERE user_id=:id").param("id",target).update(); ids.forEach { jdbc.sql("INSERT INTO rbac_user_role(user_id,role_id) VALUES (:user,:role)").param("user",target).param("role",it).update() }; if(!hasOwner(workspace(actor))) throw LastOwnerProtectedException(); audit("rbac.user.roles.updated",actor) }
    fun workspace(userId: UUID): UUID = jdbc.sql("SELECT COALESCE(workspace_owner_id,id) FROM user_account WHERE id=:id").param("id",userId).query(UUID::class.java).single()
    fun deactivate(actor: UUID,id:UUID, enabled:Boolean) { require(actor,"users:update"); val owner=workspace(actor); if(id==owner || (isOwner(id) && countOwners(owner)<=1)) throw LastOwnerProtectedException(); jdbc.sql("UPDATE user_account SET enabled=:enabled, updated_at=:now WHERE id=:id AND (id=:owner OR workspace_owner_id=:owner)").param("enabled",enabled).param("now",clock.instant()).param("id",id).param("owner",owner).update(); if(!enabled) jdbc.sql("UPDATE auth_session SET revoked_at=:now WHERE user_id=:id AND revoked_at IS NULL").param("now",clock.instant()).param("id",id).update(); audit(if(enabled)"rbac.user.reactivated" else "rbac.user.deactivated",actor) }
    private fun hasOwner(owner:UUID)=countOwners(owner)>0
    private fun countOwners(owner:UUID)=jdbc.sql("SELECT COUNT(*) FROM user_account u LEFT JOIN rbac_user_role ur ON ur.user_id=u.id LEFT JOIN rbac_role r ON r.id=ur.role_id AND r.role_key='OWNER' WHERE u.enabled AND (u.id=:owner OR u.workspace_owner_id=:owner) AND (r.role_key='OWNER' OR u.workspace_owner_id IS NULL)").param("owner",owner).query(Int::class.java).single()
    private fun roleKey(id:UUID)=jdbc.sql("SELECT role_key FROM rbac_role WHERE id=:id").param("id",id).query(String::class.java).single()
    private fun roleRow(owner:UUID,id:UUID)=jdbc.sql("SELECT id, role_key, display_name, system_role FROM rbac_role WHERE id=:id AND installation_owner_id=:owner").param("id",id).param("owner",owner).query { rs,_ -> RoleView(rs.getObject(1,UUID::class.java),rs.getString(2),rs.getString(3),rs.getBoolean(4),emptySet(),0) }.optional().orElseThrow{RoleNotFoundException()}
    private fun role(id:UUID,key:String,name:String,system:Boolean,owner:UUID)=RoleView(id,key,name,system,jdbc.sql("SELECT permission_key FROM rbac_role_permission WHERE role_id=:id").param("id",id).query(String::class.java).list().mapNotNull { it }.toSet(),jdbc.sql("SELECT COUNT(*) FROM rbac_user_role WHERE role_id=:id").param("id",id).query(Int::class.java).single())
    private fun user(id:UUID,name:String,enabled:Boolean)=UserView(id,name,enabled,jdbc.sql("SELECT r.role_key FROM rbac_user_role ur JOIN rbac_role r ON r.id=ur.role_id WHERE ur.user_id=:id ORDER BY r.role_key").param("id",id).query(String::class.java).list().mapNotNull { it },permissions(id))
    private fun setPermissions(owner:UUID,id:UUID,keys:Set<String>) { jdbc.sql("DELETE FROM rbac_role_permission WHERE role_id=:id").param("id",id).update(); keys.forEach { jdbc.sql("INSERT INTO rbac_role_permission(role_id,permission_key) VALUES (:id,:key)").param("id",id).param("key",it).update() } }
    private fun validatePermissions(keys:Set<String>) { val valid=permissionCatalog().map { it.key }.toSet(); if(!valid.containsAll(keys)) throw PermissionNotFoundException() }
    private fun audit(type:String,actor:UUID)=activity.record(ActivityCategory.SECURITY,type,ActivityStatus.SUCCEEDED,ActivityActorType.USER,"kyrion-core",type,actor.toString(),ownerId=workspace(actor))
}

fun HttpServletRequest.authenticatedUserId() = getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? UUID ?: throw UnauthenticatedException()

@RestController
@RequestMapping("/v1/rbac")
class RbacController(private val rbac:RbacService) {
    @GetMapping("/permissions") fun permissions(request:HttpServletRequest):List<PermissionDefinition>{ val id=request.authenticatedUserId(); rbac.require(id,"permissions:read"); return rbac.permissionCatalog() }
    @GetMapping("/roles") fun roles(request:HttpServletRequest):List<RoleView>{ val id=request.authenticatedUserId(); rbac.require(id,"roles:read"); return rbac.roles(rbac.workspace(id)) }
    @PostMapping("/roles") @ResponseStatus(HttpStatus.CREATED) fun create(@Valid @RequestBody body:RoleRequest,request:HttpServletRequest):RoleView { val actor=request.authenticatedUserId(); rbac.require(actor,"roles:create"); return rbac.createRole(actor,body) }
    @PutMapping("/roles/{id}") fun update(@PathVariable id:UUID,@Valid @RequestBody body:RoleRequest,request:HttpServletRequest):RoleView { val actor=request.authenticatedUserId(); rbac.require(actor,"roles:update"); return rbac.updateRole(actor,id,body) }
    @DeleteMapping("/roles/{id}") @ResponseStatus(HttpStatus.NO_CONTENT) fun delete(@PathVariable id:UUID,request:HttpServletRequest){ val actor=request.authenticatedUserId(); rbac.require(actor,"roles:delete"); rbac.deleteRole(actor,id) }
    @GetMapping("/users") fun users(request:HttpServletRequest):List<UserView>{ val id=request.authenticatedUserId(); rbac.require(id,"users:read"); return rbac.users(rbac.workspace(id)) }
    @PutMapping("/users/{id}/roles") @ResponseStatus(HttpStatus.NO_CONTENT) fun assign(@PathVariable id:UUID,@RequestBody body:RoleAssignmentRequest,request:HttpServletRequest)=rbac.assignRoles(request.authenticatedUserId(),id,body.roleIds)
    @PutMapping("/users/{id}/enabled") @ResponseStatus(HttpStatus.NO_CONTENT) fun enabled(@PathVariable id:UUID,@RequestParam value:Boolean,request:HttpServletRequest)=rbac.deactivate(request.authenticatedUserId(),id,value)
}

@RestControllerAdvice
class RbacErrorHandler {
    @ExceptionHandler(ForbiddenException::class) @ResponseStatus(HttpStatus.FORBIDDEN) fun forbidden()=mapOf("code" to "FORBIDDEN")
    @ExceptionHandler(RoleNotFoundException::class) @ResponseStatus(HttpStatus.NOT_FOUND) fun roleMissing()=mapOf("code" to "ROLE_NOT_FOUND")
    @ExceptionHandler(PermissionNotFoundException::class) @ResponseStatus(HttpStatus.BAD_REQUEST) fun permissionMissing()=mapOf("code" to "PERMISSION_NOT_FOUND")
    @ExceptionHandler(RoleInUseException::class) @ResponseStatus(HttpStatus.CONFLICT) fun roleInUse()=mapOf("code" to "ROLE_IN_USE")
    @ExceptionHandler(LastOwnerProtectedException::class) @ResponseStatus(HttpStatus.CONFLICT) fun lastOwner()=mapOf("code" to "LAST_OWNER_PROTECTED")
    @ExceptionHandler(SystemRoleProtectedException::class) @ResponseStatus(HttpStatus.CONFLICT) fun systemRole()=mapOf("code" to "SYSTEM_ROLE_PROTECTED")
}
