package dev.kyrion.core.ai

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class AiConfigurationInputTest {
    @Test
    fun `privacy flags require explicit JSON booleans and unknown input fails closed`() {
        for (raw in listOf(
            """{"localOnly":null}""",
            """{"localOnly":"false"}""",
            """{"localOnly":0}""",
            """{"unexpected":true}""",
            """{} {"localOnly":false}"""
        )) {
            assertThrows(Exception::class.java) { strictAiJson.readValue(raw, AiPreferences::class.java) }
        }
        assertTrue(strictAiJson.readValue("{}", AiPreferences::class.java).localOnly)
        assertFalse(strictAiJson.readValue("""{"localOnly":false}""", AiPreferences::class.java).localOnly)
    }
}
