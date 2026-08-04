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
) : HandlerInterceptor {
    override fun preHandle(request: HttpServletRequest, response: HttpServletResponse, handler: Any): Boolean {
        val header = request.getHeader("Authorization")
        val token = header?.takeIf { it.startsWith("Bearer ") }?.substring(7)
        val user = token?.let(authentication::authenticate)
        if (user != null) {
            request.setAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE, user.id)
            return true
        }
        response.status = HttpServletResponse.SC_UNAUTHORIZED
        response.contentType = "application/json"
        response.writer.write("{\"code\":\"UNAUTHENTICATED\"}")
        return false
    }
}

const val AUTHENTICATED_USER_ID_ATTRIBUTE = "kyrion.authenticatedUserId"

@Configuration
class AuthenticatedRouteConfiguration(
    private val interceptor: AuthenticatedRouteInterceptor,
) : WebMvcConfigurer {
    override fun addInterceptors(registry: InterceptorRegistry) {
        registry.addInterceptor(interceptor).addPathPatterns(
            "/v1/activity/**", "/v1/conversations/**", "/v1/memory/**", "/v1/integrations/**",
        )
    }
}
