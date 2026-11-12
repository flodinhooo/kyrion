package dev.kyrion.core.security

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import com.nimbusds.jose.JWSAlgorithm
import com.nimbusds.jose.jwk.JWKSet
import com.nimbusds.jose.jwk.source.ImmutableJWKSet
import com.nimbusds.jose.proc.JWSVerificationKeySelector
import com.nimbusds.jose.proc.SecurityContext
import com.nimbusds.jwt.SignedJWT
import com.nimbusds.oauth2.sdk.id.ClientID
import com.nimbusds.oauth2.sdk.id.Issuer
import com.nimbusds.openid.connect.sdk.validators.IDTokenValidator
import org.springframework.beans.factory.annotation.Value
import org.springframework.stereotype.Component
import java.net.URI
import java.net.URLEncoder
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.time.Duration
import java.time.Instant
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.util.concurrent.CompletableFuture
import java.util.concurrent.CompletionStage
import java.util.concurrent.Flow
import java.util.concurrent.TimeUnit

data class DeviceAuthorization(
    val deviceCode: String, val userCode: String, val verificationUri: String,
    val expiresIn: Long, val interval: Long,
)

data class ConfirmedCentralIdentity(
    val issuer: String, val subject: String, val expiresAt: Instant = Instant.now().plusSeconds(900),
)

interface CentralIdentityProvider {
    fun available(): Boolean
    fun startDevice(): DeviceAuthorization
    fun pollDevice(deviceCode: String): ConfirmedCentralIdentity?
}

/** Public client: no client secret, callback relay, password grant or refresh-token storage. */
@Component
class KeycloakCentralIdentityProvider(
    @Value("\${KYRION_CENTRAL_ENABLED:false}") private val enabled: Boolean = false,
    @Value("\${KYRION_CENTRAL_ISSUER:}") private val issuer: String = "",
    @Value("\${KYRION_CENTRAL_CLIENT_ID:kyrion-local}") private val clientId: String = "kyrion-local",
    @Value("\${KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP:false}") private val allowLoopbackHttp: Boolean = false,
    private val proofCache: CentralProofCache? = null,
) : CentralIdentityProvider {
    private val mapper = jacksonObjectMapper()
    private val http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3))
        .followRedirects(HttpClient.Redirect.NEVER).build()
    private var cached: Pair<Instant, JsonNode>? = null

    init {
        if (enabled) {
            require(clientId.matches(Regex("[A-Za-z0-9._-]{1,120}"))) { "KYRION_CENTRAL_CLIENT_ID is invalid" }
            require(issuer.length <= 512 && runCatching { checkedUri(issuer); !issuer.endsWith('/') }.getOrDefault(false)) {
                "KYRION_CENTRAL_ISSUER must be an exact HTTPS issuer without trailing slash; explicit loopback HTTP is development-only"
            }
        }
    }

    override fun available() = enabled

    override fun startDevice(): DeviceAuthorization = guarded {
        val metadata = metadata()
        val response = post(
            endpoint(metadata, "device_authorization_endpoint"),
            mapOf("client_id" to clientId, "scope" to "openid email profile")
        )
        if (response.first != 200) throw CentralIdentityException("CENTRAL_UNAVAILABLE")
        val body = response.second
        val verification = checkedUri(requiredText(body, "verification_uri", 2048))
        if (!sameOrigin(verification, URI(issuer))) throw CentralIdentityException("CENTRAL_INVALID_RESPONSE")
        DeviceAuthorization(
            requiredText(body, "device_code", 4096), requiredText(body, "user_code", 128), verification.toString(),
            positiveNumber(body, "expires_in", 3600),
            if (body.has("interval")) positiveNumber(body, "interval", 60) else 5,
        )
    }

    override fun pollDevice(deviceCode: String): ConfirmedCentralIdentity? = guarded {
        require(deviceCode.length in 1..4096)
        val metadata = metadata()
        val (status, body) = post(endpoint(metadata, "token_endpoint"), mapOf(
            "client_id" to clientId, "device_code" to deviceCode,
            "grant_type" to "urn:ietf:params:oauth:grant-type:device_code",
        ))
        if (status == 400) {
            when (body.path("error").asText()) {
                "authorization_pending" -> return@guarded null
                "slow_down" -> throw CentralIdentityException("CENTRAL_SLOW_DOWN")
                "access_denied", "expired_token" -> throw CentralIdentityException("CENTRAL_DENIED")
            }
        }
        if (status != 200) throw CentralIdentityException("CENTRAL_UNAVAILABLE")
        val jwt = SignedJWT.parse(requiredText(body, "id_token", 32768))
        // Fetch keys only from validated same-origin discovery; never trust token jku/x5u.
        val keys = JWKSet.parse(get(endpoint(metadata, "jwks_uri")).toString())
        val selector = JWSVerificationKeySelector<SecurityContext>(JWSAlgorithm.RS256, ImmutableJWKSet(keys))
        val validator = IDTokenValidator(Issuer(issuer), ClientID(clientId), selector, null)
        // Bound issuer iat/nbf clock differences; expiry is still checked strictly below.
        validator.maxClockSkew = 30
        // RFC 8628 has no browser callback/nonce; the confidential device code binds this response.
        val claims = validator.validate(jwt, null)
        val now = Instant.now()
        val expires = claims.expirationTime.toInstant()
        val issued = claims.issueTime.toInstant()
        if (!expires.isAfter(now) || issued.isAfter(now.plusSeconds(30)) ||
            !claims.subject.value.matches(Regex("[\\x21-\\x7E]{1,255}")) ||
            (claims.authorizedParty != null && claims.authorizedParty.value != clientId)) {
            throw CentralIdentityException("CENTRAL_INVALID_RESPONSE")
        }
        fun bounded(value: String?, limit: Int): String? =
            value?.trim()?.takeIf { it.isNotEmpty() && it.length <= limit && it.none(Char::isISOControl) }

        val email =
            bounded(claims.getStringClaim("email"), 254)?.takeIf { claims.getBooleanClaim("email_verified") == true }
        val name =
            bounded(claims.getStringClaim("name"), 160) ?: bounded(claims.getStringClaim("preferred_username"), 160)
        proofCache?.remember(
            CentralDisplayProof(
                issuer,
                claims.subject.value,
                email,
                name,
                body.path("access_token").takeIf { it.isTextual }?.asText()?.takeIf { it.length <= 32768 },
                expires
            )
        )
        ConfirmedCentralIdentity(issuer, claims.subject.value, expires)
    }

    @Synchronized
    private fun metadata(): JsonNode {
        if (!enabled) throw CentralIdentityException("CENTRAL_DISABLED")
        cached?.takeIf { it.first.isAfter(Instant.now()) }?.let { return it.second }
        val document = get(checkedUri("$issuer/.well-known/openid-configuration"))
        if (document.path("issuer").asText() != issuer) throw CentralIdentityException("CENTRAL_INVALID_RESPONSE")
        for (field in listOf("device_authorization_endpoint", "token_endpoint", "jwks_uri")) endpoint(document, field)
        cached = Instant.now().plusSeconds(300) to document
        return document
    }

    private fun endpoint(document: JsonNode, field: String): URI = checkedUri(requiredText(document, field, 2048)).also {
        if (!sameOrigin(it, URI(issuer))) throw CentralIdentityException("CENTRAL_INVALID_RESPONSE")
    }

    private fun checkedUri(value: String): URI = URI(value).also {
        require(it.host != null && it.userInfo == null && it.fragment == null && it.query == null)
        require(it.scheme == "https" || (allowLoopbackHttp && it.scheme == "http" && it.host in setOf("localhost", "127.0.0.1", "[::1]")))
    }

    private fun sameOrigin(a: URI, b: URI) = a.scheme == b.scheme && a.host == b.host && a.port == b.port

    private fun get(uri: URI): JsonNode {
        val (status, body) = send(HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(5)).GET().build())
        if (status != 200) throw CentralIdentityException("CENTRAL_UNAVAILABLE")
        return body
    }

    private fun post(uri: URI, fields: Map<String, String>): Pair<Int, JsonNode> = send(
        HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(5))
            .header("Content-Type", "application/x-www-form-urlencoded")
            .POST(HttpRequest.BodyPublishers.ofString(fields.entries.joinToString("&") {
                "${URLEncoder.encode(it.key, Charsets.UTF_8)}=${URLEncoder.encode(it.value, Charsets.UTF_8)}"
            })).build(),
    )

    private fun send(request: HttpRequest): Pair<Int, JsonNode> {
        val body = LimitedIdentityBody()
        val pending = http.sendAsync(request) { body }
        try {
            // HttpRequest.timeout alone does not bound reads after response headers.
            val response = pending.get(6, TimeUnit.SECONDS)
            return response.statusCode() to mapper.readTree(response.body())
        } finally {
            body.cancel()
            if (!pending.isDone) pending.cancel(true)
        }
    }

    private fun requiredText(body: JsonNode, field: String, limit: Int): String {
        val node = body.path(field)
        if (!node.isTextual || node.asText().isBlank() || node.asText().length > limit) throw CentralIdentityException("CENTRAL_INVALID_RESPONSE")
        return node.asText()
    }

    private fun positiveNumber(body: JsonNode, field: String, maximum: Long): Long {
        val node = body.path(field)
        if (!node.isIntegralNumber || !node.canConvertToLong() || node.asLong() !in 1..maximum) throw CentralIdentityException("CENTRAL_INVALID_RESPONSE")
        return node.asLong()
    }

    private fun <T> guarded(block: () -> T): T {
        if (!enabled) throw CentralIdentityException("CENTRAL_DISABLED")
        return try { block() } catch (e: CentralIdentityException) { throw e }
        catch (_: InterruptedException) { Thread.currentThread().interrupt(); throw CentralIdentityException("CENTRAL_UNAVAILABLE") }
        catch (_: Exception) { throw CentralIdentityException("CENTRAL_UNAVAILABLE") }
    }
}

/** Cancels oversized responses while streaming, without allocating an unbounded byte array. */
internal class LimitedIdentityBody : HttpResponse.BodySubscriber<ByteArray> {
    private val completed = CompletableFuture<ByteArray>()
    private val output = ByteArrayOutputStream()
    @Volatile private var subscription: Flow.Subscription? = null
    @Volatile private var cancelled = false
    override fun getBody(): CompletionStage<ByteArray> = completed
    override fun onSubscribe(value: Flow.Subscription) {
        subscription = value
        if (cancelled) value.cancel() else value.request(1)
    }
    override fun onNext(items: List<ByteBuffer>) {
        for (item in items) {
            if (item.remaining() > 131072 - output.size()) {
                completed.completeExceptionally(CentralIdentityException("CENTRAL_INVALID_RESPONSE"))
                cancel()
                return
            }
            val bytes = ByteArray(item.remaining())
            item.get(bytes)
            output.write(bytes)
        }
        subscription?.request(1)
    }
    override fun onComplete() { completed.complete(output.toByteArray()) }
    override fun onError(error: Throwable) { completed.completeExceptionally(error) }
    fun cancel() { cancelled = true; subscription?.cancel() }
}
