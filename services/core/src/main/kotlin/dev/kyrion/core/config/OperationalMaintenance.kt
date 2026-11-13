package dev.kyrion.core.config

import jakarta.servlet.FilterChain
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.springframework.beans.factory.annotation.Value
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty
import org.springframework.context.annotation.Configuration
import org.springframework.core.Ordered
import org.springframework.core.annotation.Order
import org.springframework.scheduling.annotation.EnableScheduling
import org.springframework.stereotype.Component
import org.springframework.web.filter.OncePerRequestFilter

@Configuration
@EnableScheduling
@ConditionalOnProperty(name = ["kyrion.operational.maintenance"], havingValue = "false", matchIfMissing = true)
class CoreScheduling

/** Host-only health/migration start; it never grants access to an application API. */
@Component
@Order(Ordered.HIGHEST_PRECEDENCE)
class OperationalMaintenanceFilter(
    @Value("\${kyrion.operational.maintenance:false}") private val enabled: Boolean,
) : OncePerRequestFilter() {
    override fun doFilterInternal(
        request: HttpServletRequest,
        response: HttpServletResponse,
        filterChain: FilterChain,
    ) {
        val health = request.servletPath in setOf(
            "/actuator/health", "/actuator/health/liveness", "/actuator/health/readiness",
        ) && request.method in setOf("GET", "HEAD")
        if (!enabled || health) {
            filterChain.doFilter(request, response)
            return
        }
        response.status = HttpServletResponse.SC_SERVICE_UNAVAILABLE
        response.contentType = "application/json"
        response.characterEncoding = "UTF-8"
        response.setHeader("Cache-Control", "no-store")
        response.setHeader("Retry-After", "60")
        response.writer.write("{\"code\":\"OPERATIONAL_MAINTENANCE\"}")
    }
}
