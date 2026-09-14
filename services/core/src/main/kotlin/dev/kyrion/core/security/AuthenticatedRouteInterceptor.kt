package dev.kyrion.core.security

import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.springframework.context.annotation.Configuration
import org.springframework.stereotype.Component
import org.springframework.web.servlet.HandlerInterceptor
import org.springframework.web.servlet.config.annotation.InterceptorRegistry
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer

@Component
class AuthenticatedRouteInterceptor(
    private val authentication: LocalAuthenticationService,
    private val rbac: RbacService,
) : HandlerInterceptor {
    override fun preHandle(request: HttpServletRequest, response: HttpServletResponse, handler: Any): Boolean {
        val header = request.getHeader("Authorization")
        val token = header?.takeIf { it.startsWith("Bearer ") }?.substring(7)
        val user = token?.let(authentication::authenticate)
        if (user != null) {
            request.setAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE, user.id)
            request.setAttribute(WORKSPACE_OWNER_ID_ATTRIBUTE, user.resourceOwnerId)
            permissionFor(request.requestURI, request.method)?.let { permission ->
                try { rbac.require(user.id, permission) } catch (_: ForbiddenException) {
                    response.status = HttpServletResponse.SC_FORBIDDEN
                    response.contentType = "application/json"
                    response.writer.write("{\"code\":\"FORBIDDEN\"}")
                    return false
                }
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
    path.startsWith("/v1/rbac/permissions") -> "permissions:read"
    path.startsWith("/v1/rbac/roles") -> when (method) { "GET" -> "roles:read"; "POST" -> "roles:create"; "PUT", "PATCH" -> "roles:update"; "DELETE" -> "roles:delete"; else -> null }
    path.startsWith("/v1/rbac/users") -> when (method) { "GET" -> "users:read"; "PUT", "PATCH" -> "users:update"; else -> null }
    path.startsWith("/v1/activity") -> "activity_log:read"
    path.startsWith("/v1/conversations") -> when (method) { "GET" -> "conversations:read"; "POST" -> "conversations:create"; "PUT", "PATCH" -> "conversations:update"; "DELETE" -> "conversations:delete"; else -> null }
    path.startsWith("/v1/memory") -> when (method) { "GET" -> "personal_memories:read"; "POST" -> "personal_memories:create"; "PUT", "PATCH" -> "personal_memories:update"; "DELETE" -> "personal_memories:delete"; else -> null }
    path.startsWith("/v1/home/rooms") -> when (method) { "GET" -> "rooms:read"; "POST" -> "rooms:create"; "PUT", "PATCH" -> "rooms:update"; "DELETE" -> "rooms:delete"; else -> null }
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
            "/v1/devices/**",
            "/v1/gateways/**",
            "/v1/voice-satellites/**",
            "/v1/actions/**",
            "/v1/retention/**",
            "/v1/backups/**",
            "/v1/rbac/**",
        )
    }
}
