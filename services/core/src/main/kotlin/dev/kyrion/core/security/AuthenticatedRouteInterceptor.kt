package dev.kyrion.core.security

import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.springframework.context.annotation.Configuration
import org.springframework.stereotype.Component
import org.springframework.web.servlet.HandlerInterceptor
import org.springframework.web.servlet.config.annotation.InterceptorRegistry
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer
import dev.kyrion.core.activity.*

@Component
class AuthenticatedRouteInterceptor(
    private val authentication: LocalAuthenticationService,
    private val rbac: RbacService,
    private val activity: ActivityService,
) : HandlerInterceptor {
    override fun preHandle(request: HttpServletRequest, response: HttpServletResponse, handler: Any): Boolean {
        if ((request.requestURI.startsWith("/v1/space") || request.requestURI.startsWith("/v1/identity"))) response.setHeader("Cache-Control", "no-store")
        val header = request.getHeader("Authorization")
        val token = header?.takeIf { it.startsWith("Bearer ") }?.substring(7)
        val user = token?.let(authentication::authenticate)
        if (user != null) {
            request.setAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE, user.id)
            request.setAttribute(WORKSPACE_OWNER_ID_ATTRIBUTE, user.resourceOwnerId)
            val permission = permissionFor(request.requestURI, if (request.method == "HEAD") "GET" else request.method)
            try {
                if (permission == null) throw ForbiddenException()
                if (permission != "identity:self") rbac.require(user.id, permission)
            } catch (_: ForbiddenException) {
                    activity.record(ActivityCategory.SECURITY, "security.permission.denied", ActivityStatus.DENIED,
                        ActivityActorType.USER, "kyrion-core", permission ?: "route.unmapped", user.id.toString(), ownerId = user.resourceOwnerId)
                    response.status = HttpServletResponse.SC_FORBIDDEN
                    response.contentType = "application/json"
                    response.writer.write("{\"code\":\"FORBIDDEN\"}")
                    return false
            }
            return true
        }
        response.status = HttpServletResponse.SC_UNAUTHORIZED
        response.contentType = "application/json"
        response.writer.write("{\"code\":\"UNAUTHENTICATED\"}")
        return false
    }

}

internal fun permissionFor(path: String, method: String): String? = when {
    path == "/v1/identity/email" && method in setOf("GET", "POST") -> "identity:self"
    path == "/v1/identity/email/verify" && method == "POST" -> "identity:self"
    path == "/v1/identity/business" && method in setOf("GET", "PUT") -> "system_settings:update"
    path in setOf("/v1/identity/business/challenge", "/v1/identity/business/verify", "/v1/identity/business/suspend") && method == "POST" -> "system_settings:update"
    path == "/v1/space" -> when (method) { "GET" -> "devices:read"; "PUT" -> "system_settings:update"; else -> null }
    path.startsWith("/v1/space/invitations") -> when (method) {
        "GET", "POST", "DELETE" -> "invitations:create"; else -> null
    }
    path == "/v1/ai/policy" -> when (method) {
        "GET" -> "system_settings:read"; "PUT" -> "system_settings:update"; else -> null
    }

    path == "/v1/ai/preferences" -> when (method) {
        "GET" -> "conversations:read"; "PUT" -> "conversations:update"; else -> null
    }

    path == "/v1/ai/usage" && method == "GET" -> "conversations:read"
    path in setOf("/v1/ai/route", "/v1/ai/chat/stream") && method == "POST" -> "conversations:create"
    path.startsWith("/v1/rbac/permissions") -> "permissions:read"
    path.startsWith("/v1/rbac/roles") -> when (method) { "GET" -> "roles:read"; "POST" -> "roles:create"; "PUT", "PATCH" -> "roles:update"; "DELETE" -> "roles:delete"; else -> null }
    path.startsWith("/v1/rbac/users") -> when (method) { "GET" -> "users:read"; "PUT", "PATCH" -> "users:update"; else -> null }
    path.startsWith("/v1/calendar/") || path.startsWith("/v1/integrations/google/calendar/") -> when (method) { "GET" -> "calendar:read"; "POST" -> "calendar:create"; "PUT", "PATCH" -> "calendar:update"; "DELETE" -> "calendar:delete"; else -> null }
    path.startsWith("/v1/activity") -> "activity_log:read"
    path.startsWith("/v1/conversations") -> when (method) { "GET" -> "conversations:read"; "POST" -> "conversations:create"; "PUT", "PATCH" -> "conversations:update"; "DELETE" -> "conversations:delete"; else -> null }
    path.startsWith("/v1/memory") -> when (method) { "GET" -> "personal_memories:read"; "POST" -> "personal_memories:create"; "PUT", "PATCH" -> "personal_memories:update"; "DELETE" -> "personal_memories:delete"; else -> null }
    path.startsWith("/v1/home/rooms") -> when (method) { "GET" -> "rooms:read"; "POST" -> "rooms:create"; "PUT", "PATCH" -> "rooms:update"; "DELETE" -> "rooms:delete"; else -> null }
    path.startsWith("/v1/home/connections") -> when (method) { "GET" -> "integrations:read"; "POST" -> "integrations:create"; "PUT", "PATCH" -> "integrations:update"; "DELETE" -> "integrations:delete"; else -> null }
    path.startsWith("/v1/devices") -> when (method) { "GET" -> "devices:read"; "POST" -> "devices:create"; "PUT", "PATCH" -> "devices:update"; "DELETE" -> "devices:delete"; else -> null }
    path.startsWith("/v1/device-commands") || path.startsWith("/v1/actions") -> "devices:execute"
    path.startsWith("/v1/gateways") -> when (method) { "GET" -> "gateways:read"; "POST" -> "gateways:execute"; "PUT", "PATCH" -> "gateways:update"; "DELETE" -> "gateways:delete"; else -> null }
    path.startsWith("/v1/voice-satellites") || path.startsWith("/v1/voice-satellite") -> "voice_satellites:execute"
    path.startsWith("/v1/integrations") || path.startsWith("/v1/integration-catalog") -> when (method) { "GET" -> "integrations:read"; "POST" -> "integrations:create"; "PUT", "PATCH" -> "integrations:update"; "DELETE" -> "integrations:delete"; else -> null }
    path.startsWith("/v1/backups") -> when (method) { "GET" -> "backups:read"; "POST" -> "backups:create"; "DELETE" -> "backups:delete"; else -> null }
    path.startsWith("/v1/retention") || path.startsWith("/v1/system-services") -> "system_settings:update"
    else -> null
}

const val AUTHENTICATED_USER_ID_ATTRIBUTE = "kyrion.authenticatedUserId"
const val WORKSPACE_OWNER_ID_ATTRIBUTE = "kyrion.workspaceOwnerId"

@Configuration
class AuthenticatedRouteConfiguration(
    private val interceptor: AuthenticatedRouteInterceptor,
) : WebMvcConfigurer {
    override fun addInterceptors(registry: InterceptorRegistry) {
        registry.addInterceptor(interceptor).addPathPatterns(
            "/v1/activity/**", "/v1/conversations/**", "/v1/memory/**", "/v1/integrations/**", "/v1/integration-catalog/**", "/v1/home/**",
            "/v1/device-commands/**",
            "/v1/devices/**", "/v1/calendar/**",
            "/v1/gateways/**",
            "/v1/voice-satellites/**",
            "/v1/actions/**",
            "/v1/retention/**",
            "/v1/backups/**",
            "/v1/rbac/**",
            "/v1/space/**",
            "/v1/identity/**",
            "/v1/ai/**",
        )
    }
}
