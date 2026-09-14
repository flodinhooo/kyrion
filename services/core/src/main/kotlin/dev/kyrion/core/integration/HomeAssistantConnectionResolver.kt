package dev.kyrion.core.integration

import org.springframework.stereotype.Service
import java.util.UUID

/** Selects the complete HA credential source; URL and token are never mixed. */
@Service
class HomeAssistantConnectionResolver(
    private val store: HomeAssistantConnectionStore,
    private val development: HomeAssistantDevelopmentConfiguration,
) {
    fun resolve(ownerId: UUID): HomeAssistantConnectionConfig? =
        store.findForOwner(ownerId) ?: development.connectionOrNull(ownerId)
}

internal fun HomeAssistantDevelopmentConfiguration.connectionOrNull(ownerId: UUID): HomeAssistantConnectionConfig? =
    runCatching { connection(ownerId) }.getOrNull()
