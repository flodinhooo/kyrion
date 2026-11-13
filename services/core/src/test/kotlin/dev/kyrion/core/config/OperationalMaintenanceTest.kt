package dev.kyrion.core.config

import jakarta.servlet.FilterChain
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import org.springframework.context.annotation.AnnotationConfigApplicationContext
import org.springframework.core.env.MapPropertySource
import org.springframework.mock.web.MockHttpServletRequest
import org.springframework.mock.web.MockHttpServletResponse
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.scheduling.annotation.ScheduledAnnotationBeanPostProcessor
import java.util.concurrent.atomic.AtomicInteger

class OperationalMaintenanceTest {
    @Test
    fun `maintenance rejects application routes before delegation including login and control`() {
        val filter = OperationalMaintenanceFilter(true)
        for ((method, path) in listOf(
            "POST" to "/v1/auth/login", "GET" to "/v1/space",
            "POST" to "/v1/actions/execute", "POST" to "/actuator/health",
            "GET" to "/actuator/health/../v1/space", "GET" to "/unknown",
        )) {
            val request = MockHttpServletRequest(method, path).apply { servletPath = path }
            val response = MockHttpServletResponse()
            var called = false
            filter.doFilter(request, response, FilterChain { _, _ -> called = true })
            assertFalse(called, path)
            assertEquals(503, response.status, path)
            assertEquals("{\"code\":\"OPERATIONAL_MAINTENANCE\"}", response.contentAsString)
            assertEquals("no-store", response.getHeader("Cache-Control"))
        }
    }

    @Test
    fun `exact read-only health routes remain delegated and normal mode keeps existing auth`() {
        for ((enabled, method, path) in listOf(
            Triple(true, "GET", "/actuator/health"),
            Triple(true, "HEAD", "/actuator/health/readiness"),
            Triple(false, "POST", "/v1/auth/login"),
        )) {
            val request = MockHttpServletRequest(method, path).apply { servletPath = path }
            var called = false
            OperationalMaintenanceFilter(enabled).doFilter(
                request, MockHttpServletResponse(), FilterChain { _, _ -> called = true },
            )
            assertTrue(called)
        }
    }

    @Test
    fun `maintenance disables global scheduled work and normal mode restores registration`() {
        for (maintenance in listOf(true, false)) {
            AnnotationConfigApplicationContext().use { context ->
                context.environment.propertySources.addFirst(
                    MapPropertySource("test", mapOf("kyrion.operational.maintenance" to maintenance.toString())),
                )
                context.register(CoreScheduling::class.java, ScheduledProbe::class.java)
                context.refresh()
                assertEquals(!maintenance, context.getBeansOfType(ScheduledAnnotationBeanPostProcessor::class.java).isNotEmpty())
                val probe = context.getBean(ScheduledProbe::class.java)
                if (maintenance) {
                    assertEquals(0, probe.calls.get())
                } else {
                    val deadline = System.nanoTime() + 2_000_000_000L
                    while (probe.calls.get() == 0 && System.nanoTime() < deadline) Thread.sleep(10)
                    assertTrue(probe.calls.get() > 0)
                }
            }
        }
    }

    class ScheduledProbe {
        val calls = AtomicInteger()

        @Scheduled(fixedDelay = 10)
        fun tick() { calls.incrementAndGet() }
    }
}
