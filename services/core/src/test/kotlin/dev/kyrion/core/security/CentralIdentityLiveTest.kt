package dev.kyrion.core.security

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable
import java.nio.file.Files
import java.nio.file.Path
import java.time.Instant

/** Opt-in actual Keycloak transport; helper browser authorizes only the public user code. */
@EnabledIfEnvironmentVariable(named = "KYRION_IDENTITY_LIVE", matches = "true")
class CentralIdentityLiveTest {
    @Test fun `Core verifies a real Keycloak device identity`() {
        val issuer = "http://localhost:8089/realms/kyrion"
        val provider = KeycloakCentralIdentityProvider(true, issuer, "kyrion-local", true)
        val device = provider.startDevice()
        val requestFile = Path.of(System.getenv("KYRION_IDENTITY_LIVE_REQUEST_FILE")
            ?: error("Set KYRION_IDENTITY_LIVE_REQUEST_FILE to an ignored path for browser coordination"))
        Files.createDirectories(requestFile.parent)
        Files.writeString(requestFile, jacksonObjectMapper().writeValueAsString(mapOf(
            "userCode" to device.userCode, "verificationUri" to device.verificationUri,
        )))
        try {
            val deadline = Instant.now().plusSeconds(120)
            var identity: ConfirmedCentralIdentity? = null
            var interval = device.interval.coerceAtLeast(5)
            while (identity == null && Instant.now().isBefore(deadline)) {
                Thread.sleep(interval * 1000)
                try { identity = provider.pollDevice(device.deviceCode) }
                catch (error: CentralIdentityException) {
                    if (error.code != "CENTRAL_SLOW_DOWN") throw error
                    interval += 5
                }
            }
            assertNotNull(identity, "Browser did not authorize the live device request before timeout")
            assertEquals(issuer, identity!!.issuer)
            assertTrue(identity.subject.isNotBlank())
            assertTrue(identity.expiresAt.isAfter(Instant.now()))
        } finally {
            Files.deleteIfExists(requestFile)
        }
    }
}
