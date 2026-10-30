package dev.kyrion.core.integration

import org.springframework.context.annotation.Configuration
import org.springframework.scheduling.annotation.EnableScheduling
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Component
import org.springframework.jdbc.core.simple.JdbcClient
import java.util.UUID

@Configuration
@EnableScheduling
class HomeAssistantScheduling

/** Reuse the bounded, serialized importer; a failed owner must not stop others. */
@Component
@org.springframework.boot.autoconfigure.condition.ConditionalOnProperty(name = ["kyrion.home-assistant.refresh-enabled"], havingValue = "true", matchIfMissing = true)
class HomeAssistantRefresh(private val jdbc: JdbcClient, private val importer: HomeAssistantImportService, private val boundary: dev.kyrion.core.security.TenantBoundary? = null) {
    @Scheduled(fixedDelayString = "\${kyrion.home-assistant.refresh-ms:30000}", initialDelay = 1000)
    fun refresh() {
        val owners = jdbc.sql("SELECT id FROM user_account WHERE workspace_owner_id IS NULL")
            .query(UUID::class.java).list().filterNotNull()
        owners.forEach { owner ->
            try {
                boundary?.workspace(owner)
                importer.refreshIfDue(owner)
            } catch (_: Exception) {
                // Importer records bounded provider failures. Do not log credentials/payloads.
            }
        }
    }
}
