package dev.kyrion.core.security

import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import com.nimbusds.jose.JWSAlgorithm
import com.nimbusds.jose.JWSHeader
import com.nimbusds.jose.crypto.RSASSASigner
import com.nimbusds.jose.jwk.JWKSet
import com.nimbusds.jose.jwk.gen.RSAKeyGenerator
import com.nimbusds.jwt.JWTClaimsSet
import com.nimbusds.jwt.SignedJWT
import com.sun.net.httpserver.HttpServer
import org.junit.jupiter.api.AfterEach
import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test
import java.net.InetSocketAddress
import java.time.Instant
import java.util.Date

/** Real HTTP and RSA verification against a synthetic issuer, NOT a live Keycloak test. */
class CentralIdentityProviderTest {
    private val mapper = jacksonObjectMapper()
    private val key = RSAKeyGenerator(2048).keyID("test-key").generate()
    private val server = HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0)
    private val issuer = "http://127.0.0.1:${server.address.port}/realm"
    private var jwt = ""
    private var tokenError: String? = null
    private var verificationUri = "$issuer/device"
    private var metadataIssuer = issuer
    private var tokenEndpoint = "$issuer/token"
    private var stallTokenBody = false
    private val releaseBody = java.util.concurrent.CountDownLatch(1)
    private val provider = KeycloakCentralIdentityProvider(true, issuer, "kyrion-local", true)

    init {
        server.createContext("/realm/.well-known/openid-configuration") { exchange ->
            val data = mapper.writeValueAsBytes(mapOf("issuer" to metadataIssuer,
                "device_authorization_endpoint" to "$issuer/device", "token_endpoint" to tokenEndpoint, "jwks_uri" to "$issuer/keys"))
            exchange.sendResponseHeaders(200, data.size.toLong()); exchange.responseBody.use { it.write(data) }
        }
        server.createContext("/realm/keys") { exchange ->
            val data = JWKSet(key.toPublicJWK()).toString().toByteArray()
            exchange.sendResponseHeaders(200, data.size.toLong()); exchange.responseBody.use { it.write(data) }
        }
        server.createContext("/realm/device") { exchange ->
            val body = exchange.requestBody.readAllBytes().toString(Charsets.UTF_8)
            assertEquals("client_id=kyrion-local&scope=openid", body)
            val data = mapper.writeValueAsBytes(mapOf("device_code" to "private-device-code", "user_code" to "USER-CODE",
                "verification_uri" to verificationUri, "expires_in" to 600, "interval" to 5))
            exchange.sendResponseHeaders(200, data.size.toLong()); exchange.responseBody.use { it.write(data) }
        }
        server.createContext("/realm/token") { exchange ->
            val body = exchange.requestBody.readAllBytes().toString(Charsets.UTF_8)
            assertTrue(body.contains("grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code"))
            assertFalse(body.contains("client_secret"))
            if (stallTokenBody) {
                exchange.sendResponseHeaders(200, 1000)
                exchange.responseBody.write('{'.code)
                exchange.responseBody.flush()
                releaseBody.await(15, java.util.concurrent.TimeUnit.SECONDS)
                exchange.close()
                return@createContext
            }
            val data = mapper.writeValueAsBytes(tokenError?.let { mapOf("error" to it) } ?: mapOf("id_token" to jwt))
            exchange.sendResponseHeaders(if (tokenError == null) 200 else 400, data.size.toLong())
            exchange.responseBody.use { it.write(data) }
        }
        server.start()
    }

    @AfterEach fun stop() = server.stop(0)

    private fun token(change: JWTClaimsSet.Builder.() -> Unit = {}): String {
        val now = Instant.now()
        val claims = JWTClaimsSet.Builder().issuer(issuer).subject("stable-subject").audience("kyrion-local")
            .issueTime(Date.from(now.minusSeconds(1))).expirationTime(Date.from(now.plusSeconds(300))).apply(change).build()
        return SignedJWT(JWSHeader.Builder(JWSAlgorithm.RS256).keyID(key.keyID).build(), claims).apply { sign(RSASSASigner(key)) }.serialize()
    }

    @Test fun `device transport and valid RSA identity without importing email`() {
        val device = provider.startDevice()
        assertEquals("USER-CODE", device.userCode)
        assertEquals("private-device-code", device.deviceCode)
        jwt = token { claim("email", "flo@example.invalid"); claim("email_verified", true) }
        val identity = provider.pollDevice(device.deviceCode)!!
        assertEquals(issuer, identity.issuer)
        assertEquals("stable-subject", identity.subject)
        assertTrue(identity.expiresAt.isAfter(Instant.now()))
    }

    @Test fun `invalid issuer audience expiration authorized party or signature fails closed`() {
        val invalid = listOf(
            token { issuer("https://attacker.invalid") }, token { audience("other-client") },
            token { expirationTime(Date.from(Instant.now().minusSeconds(120))) },
            token { claim("azp", "other-client") }, token { subject("") },
            token { issueTime(Date.from(Instant.now().plusSeconds(3600))) },
            SignedJWT(JWSHeader.Builder(JWSAlgorithm.RS256).keyID(key.keyID).build(), SignedJWT.parse(token()).jwtClaimsSet)
                .apply { sign(RSASSASigner(RSAKeyGenerator(2048).keyID(key.keyID).generate())) }.serialize(),
        )
        invalid.forEach { jwt = it; assertThrows(CentralIdentityException::class.java) { provider.pollDevice("device") } }
    }

    @Test fun `unsigned token is rejected`() {
        jwt = com.nimbusds.jwt.PlainJWT(SignedJWT.parse(token()).jwtClaimsSet).serialize()
        assertThrows(CentralIdentityException::class.java) { provider.pollDevice("device") }
    }

    @Test fun `a provider stalling after response headers has a bounded deadline`() {
        stallTokenBody = true
        try {
            assertTimeout(java.time.Duration.ofSeconds(9)) {
                assertThrows(CentralIdentityException::class.java) { provider.pollDevice("device") }
            }
        } finally { releaseBody.countDown() }
    }

    @Test fun `device pending slowdown and denial are distinct`() {
        tokenError = "authorization_pending"
        assertNull(provider.pollDevice("device"))
        tokenError = "slow_down"
        assertEquals("CENTRAL_SLOW_DOWN", assertThrows(CentralIdentityException::class.java) { provider.pollDevice("device") }.code)
        tokenError = "access_denied"
        assertEquals("CENTRAL_DENIED", assertThrows(CentralIdentityException::class.java) { provider.pollDevice("device") }.code)
    }

    @Test fun `discovery cannot change issuer or move endpoints to another origin`() {
        metadataIssuer = "https://attacker.invalid"
        assertThrows(CentralIdentityException::class.java) { provider.startDevice() }
        metadataIssuer = issuer
        tokenEndpoint = "https://attacker.invalid/token"
        assertThrows(CentralIdentityException::class.java) { provider.startDevice() }
    }

    @Test fun `verification URI cannot send user to another origin`() {
        verificationUri = "https://attacker.invalid/device"
        assertThrows(CentralIdentityException::class.java) { provider.startDevice() }
    }

    @Test fun `disabled provider needs no usable network configuration`() {
        val disabled = KeycloakCentralIdentityProvider(false, "", "", false)
        assertFalse(disabled.available())
        assertEquals("CENTRAL_DISABLED", assertThrows(CentralIdentityException::class.java) { disabled.startDevice() }.code)
        assertThrows(IllegalArgumentException::class.java) { KeycloakCentralIdentityProvider(true, issuer, "kyrion-local", false) }
        assertThrows(IllegalArgumentException::class.java) { KeycloakCentralIdentityProvider(true, "https://example.invalid/", "kyrion-local", false) }
    }
}
