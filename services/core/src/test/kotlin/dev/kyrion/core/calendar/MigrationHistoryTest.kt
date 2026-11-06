package dev.kyrion.core.calendar

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test
import java.util.zip.CRC32

class MigrationHistoryTest {
    @Test fun `V31 retains the checksum of the applied Windows development artifact`() {
        val checksum = CRC32()
        javaClass.getResourceAsStream("/db/migration/V31__bootstrap_state_and_calendar_permissions.sql")!!.bufferedReader(Charsets.UTF_8).useLines { lines ->
            lines.forEach { checksum.update(it.removePrefix("\uFEFF").toByteArray(Charsets.UTF_8)) }
        }
        assertEquals(1755433543, checksum.value.toInt())
    }
}
