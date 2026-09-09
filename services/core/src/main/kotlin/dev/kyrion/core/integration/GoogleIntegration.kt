package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.security.workspaceOwnerId
import jakarta.servlet.http.HttpServletRequest
import org.springframework.beans.factory.annotation.Value
import org.springframework.http.HttpStatus
import org.springframework.stereotype.Service
import org.springframework.web.bind.annotation.*
import java.net.URI
import java.net.URLEncoder
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.charset.StandardCharsets
import java.time.Clock
import java.time.Instant
import java.util.Base64
import java.util.UUID
import java.security.SecureRandom
import java.util.concurrent.ConcurrentHashMap

private const val GOOGLE_PROVIDER = "google"
private const val CALENDAR_READ = "calendar.read"
private val GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.readonly"

data class GoogleAuthorization(val authorizationUrl: String)
data class GoogleStatus(val configured: Boolean, val connected: Boolean, val accountName: String? = null, val reauthorizationRequired: Boolean = false)
data class GoogleToken(val accessToken: String, val refreshToken: String?, val expiresAt: Instant, val accountName: String)
data class GoogleCalendarEvent(val id: String, val summary: String, val start: String?, val end: String?)
data class GoogleCalendarEvents(val items: List<GoogleCalendarEvent>)

interface GoogleOAuthClient {
    fun exchange(code: String, redirectUri: String, clientId: String, clientSecret: String): GoogleToken
    fun refresh(refreshToken: String, clientId: String, clientSecret: String, accountName: String): GoogleToken
    fun revoke(token: String)
    fun events(accessToken: String): GoogleCalendarEvents
}

@Service
class HttpGoogleOAuthClient : GoogleOAuthClient {
    private val http = HttpClient.newHttpClient(); private val mapper = jacksonObjectMapper()
    private fun post(url: String, body: String, auth: String? = null): JsonNode {
        val builder = HttpRequest.newBuilder(URI(url)).header("Content-Type", "application/x-www-form-urlencoded").POST(HttpRequest.BodyPublishers.ofString(body)); if (auth != null) builder.header("Authorization", auth)
        val response = http.send(builder.build(), HttpResponse.BodyHandlers.ofString()); if (response.statusCode() !in 200..299) throw GoogleProviderException(response.statusCode()); return mapper.readTree(response.body())
    }
    override fun exchange(code: String, redirectUri: String, clientId: String, clientSecret: String): GoogleToken { val node = post("https://oauth2.googleapis.com/token", form(mapOf("code" to code, "client_id" to clientId, "client_secret" to clientSecret, "redirect_uri" to redirectUri, "grant_type" to "authorization_code"))); return token(node, null) }
    override fun refresh(refreshToken: String, clientId: String, clientSecret: String, accountName: String): GoogleToken { val node = post("https://oauth2.googleapis.com/token", form(mapOf("refresh_token" to refreshToken, "client_id" to clientId, "client_secret" to clientSecret, "grant_type" to "refresh_token"))); return token(node, accountName).copy(refreshToken = refreshToken) }
    override fun revoke(token: String) { post("https://oauth2.googleapis.com/revoke?token=${enc(token)}", "") }
    override fun events(accessToken: String): GoogleCalendarEvents { val request = HttpRequest.newBuilder(URI("https://www.googleapis.com/calendar/v3/calendars/primary/events?singleEvents=true&orderBy=startTime&maxResults=25")).header("Authorization", "Bearer $accessToken").GET().build(); val response = http.send(request, HttpResponse.BodyHandlers.ofString()); if (response.statusCode() !in 200..299) throw GoogleProviderException(response.statusCode()); val items = mapper.readTree(response.body()).path("items").map { GoogleCalendarEvent(it.path("id").asText(), it.path("summary").asText("(untitled)"), it.path("start").path("dateTime").asText(null), it.path("end").path("dateTime").asText(null)) }; return GoogleCalendarEvents(items) }
    private fun token(node: JsonNode, account: String?) = GoogleToken(node.path("access_token").asText().also { require(it.isNotBlank()) }, node.path("refresh_token").asText(null), Instant.now().plusSeconds(node.path("expires_in").asLong(3600)), account ?: node.path("email").asText("Google account"))
    private fun form(values: Map<String, String>) = values.entries.joinToString("&") { "${enc(it.key)}=${enc(it.value)}" }
    private fun enc(value: String) = URLEncoder.encode(value, StandardCharsets.UTF_8)
}

@Service
class GoogleIntegrationService(
    private val repository: IntegrationConnectionRepository,
    private val grants: JdbcIntegrationCapabilityGrantRepository,
    private val cipher: CredentialCipher,
    private val client: GoogleOAuthClient,
    @Value("\${kyrion.google.client-id:}") private val clientId: String,
    @Value("\${kyrion.google.client-secret:}") private val clientSecret: String,
    @Value("\${kyrion.google.redirect-uri:}") private val redirectUri: String,
    private val clock: Clock = Clock.systemUTC(),
) {
    private val random = SecureRandom(); private val pending = ConcurrentHashMap<String, Pair<UUID, Instant>>(); private val mapper = jacksonObjectMapper()
    fun configured() = clientId.isNotBlank() && clientSecret.isNotBlank() && redirectUri.isNotBlank()
    fun status(ownerId: UUID): GoogleStatus { val connection = connection(ownerId) ?: return GoogleStatus(configured(), false); val enabled = grants.findAll(ownerId, connection.id).any { it.capability == CALENDAR_READ && it.granted }; return GoogleStatus(configured(), true, connection.displayName, !enabled) }
    fun authorize(ownerId: UUID): GoogleAuthorization { if (!configured()) throw GoogleNotConfiguredException(); val bytes = ByteArray(32).also(random::nextBytes); val state = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes); pending[state] = ownerId to clock.instant().plusSeconds(600); val query = mapOf("client_id" to clientId, "redirect_uri" to redirectUri, "response_type" to "code", "scope" to "openid email profile $GOOGLE_CALENDAR_SCOPE", "access_type" to "offline", "prompt" to "consent", "state" to state).entries.joinToString("&") { "${enc(it.key)}=${enc(it.value)}" }; return GoogleAuthorization("https://accounts.google.com/o/oauth2/v2/auth?$query") }
    fun complete(ownerId: UUID, code: String, state: String): GoogleStatus { val request = pending.remove(state) ?: throw GoogleInvalidStateException(); if (request.first != ownerId || request.second.isBefore(clock.instant())) throw GoogleInvalidStateException(); val token = client.exchange(code, redirectUri, clientId, clientSecret); val id = UUID.randomUUID(); val now = clock.instant(); val payload = mapper.writeValueAsString(token); val protected = cipher.protect(payload, "$ownerId:$id:$GOOGLE_PROVIDER"); repository.save(IntegrationConnection(id, ownerId, GOOGLE_PROVIDER, token.accountName, token.accountName, protected.ciphertext, protected.nonce, protected.version, now, now)); grants.replace(ownerId, id, setOf(CALENDAR_READ), now); return GoogleStatus(true, true, token.accountName) }
    fun events(ownerId: UUID): GoogleCalendarEvents { val connection = connection(ownerId) ?: throw GoogleDisconnectedException(); if (!grants.findAll(ownerId, connection.id).any { it.capability == CALENDAR_READ && it.granted }) throw GoogleCapabilityDisabledException(); val token = token(connection); return try { client.events(token.accessToken) } catch (error: GoogleProviderException) { if (error.status != 401 || token.refreshToken == null) throw GoogleProviderUnavailableException(); val refreshed = client.refresh(token.refreshToken, clientId, clientSecret, token.accountName); saveToken(connection, refreshed); client.events(refreshed.accessToken) } }
    fun disconnect(ownerId: UUID) { val connection = connection(ownerId) ?: return; runCatching { client.revoke(token(connection).accessToken) }; grants.delete(ownerId, connection.id); repository.delete(ownerId, connection.id) }
    private fun connection(ownerId: UUID) = repository.findAll(ownerId).firstOrNull { it.provider == GOOGLE_PROVIDER }
    private fun token(connection: IntegrationConnection): GoogleToken = mapper.readValue(cipher.reveal(connection), GoogleToken::class.java)
    private fun saveToken(connection: IntegrationConnection, token: GoogleToken) { val protected = cipher.protect(mapper.writeValueAsString(token), "${connection.ownerId}:${connection.id}:$GOOGLE_PROVIDER"); repository.updateCredential(connection.ownerId, connection.id, protected, clock.instant()) }
    private fun enc(value: String) = URLEncoder.encode(value, StandardCharsets.UTF_8)
}

@RestController
@RequestMapping("/v1/integrations/google")
class GoogleIntegrationController(private val service: GoogleIntegrationService) {
    @GetMapping fun status(request: HttpServletRequest) = service.status(request.workspaceOwnerId())
    @PostMapping("/authorization") fun authorize(request: HttpServletRequest) = service.authorize(request.workspaceOwnerId())
    @PostMapping("/authorization/complete") fun complete(@RequestBody body: Map<String, String>, request: HttpServletRequest) = service.complete(request.workspaceOwnerId(), body["code"] ?: throw GoogleInvalidRequestException(), body["state"] ?: throw GoogleInvalidRequestException())
    @GetMapping("/calendar/events") fun events(request: HttpServletRequest) = service.events(request.workspaceOwnerId())
    @DeleteMapping @ResponseStatus(HttpStatus.NO_CONTENT) fun disconnect(request: HttpServletRequest) = service.disconnect(request.workspaceOwnerId())
}

class GoogleNotConfiguredException : RuntimeException(); class GoogleInvalidStateException : RuntimeException(); class GoogleInvalidRequestException : RuntimeException(); class GoogleDisconnectedException : RuntimeException(); class GoogleCapabilityDisabledException : RuntimeException(); class GoogleProviderUnavailableException : RuntimeException(); class GoogleProviderException(val status: Int) : RuntimeException()
