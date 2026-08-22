package dev.kyrion.core.capability

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Test
import java.util.UUID

class CommandedPowerStateStoreTest {
    @Test
    fun `tracks last confirmed power command per owner and device`() {
        val store = CommandedPowerStateStore()
        val owner = UUID.randomUUID()
        val device = UUID.randomUUID()

        assertNull(store.get(owner, device))
        store.record(owner, device, true)
        assertEquals(true, store.get(owner, device))
        store.record(owner, device, false)
        assertEquals(false, store.get(owner, device))
    }
}
