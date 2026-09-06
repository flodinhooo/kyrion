package dev.kyrion.core.integration

import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RestController
import java.time.Instant

data class DatabaseDiagnostic(val status: String, val observedAt: Instant, val reason: String?)

@RestController
class PlatformDiagnosticsController(private val jdbc: JdbcClient) {
    @GetMapping("/v1/integrations/platform-diagnostics/database")
    fun database(): DatabaseDiagnostic = try {
        check(jdbc.sql("SELECT 1").query(Int::class.java).single() == 1)
        DatabaseDiagnostic("healthy", Instant.now(), null)
    } catch (_: RuntimeException) {
        DatabaseDiagnostic("offline", Instant.now(), "dependency_unreachable")
    }
}
