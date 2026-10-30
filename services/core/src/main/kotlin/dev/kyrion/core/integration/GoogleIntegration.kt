package dev.kyrion.core.integration

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.security.authenticatedUserId
import dev.kyrion.core.activity.*
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
import java.time.Duration
import java.util.Base64
import java.util.UUID
import java.security.SecureRandom
import java.util.concurrent.ConcurrentHashMap

private const val GOOGLE_PROVIDER = "google"
private const val CALENDAR_READ = "calendar.read"
private const val CALENDAR_EVENT_CREATE = "calendar.event.create"
private const val CALENDAR_EVENT_UPDATE = "calendar.event.update"
private const val CALENDAR_EVENT_DELETE = "calendar.event.delete"
private val GOOGLE_CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar"

data class GoogleAuthorization(val authorizationUrl: String)
data class GoogleStatus(val configured: Boolean, val connected: Boolean, val accountName: String? = null, val reauthorizationRequired: Boolean = false)
class GoogleToken(val accessToken: String, val refreshToken: String?, val expiresAt: Instant, val accountName: String) {
    override fun toString() = "GoogleToken(accountName=$accountName, expiresAt=$expiresAt, accessToken=<redacted>, refreshToken=<redacted>)"
}
data class GoogleCalendarEvent(val id: String, val summary: String, val start: String?, val end: String?, val etag: String? = null, val status: String = "confirmed", val description: String? = null, val recurring: Boolean = false, val kyrionId: String? = null)
data class GoogleCalendarEvents(val items: List<GoogleCalendarEvent>)
data class GoogleCalendar(val id: String, val summary: String, val timeZone: String?, val accessRole: String = "reader", val primary: Boolean = false)
data class GoogleCalendars(val items: List<GoogleCalendar>)
data class GoogleCalendarEventRequest(val calendarId: String = "primary", val summary: String, val start: String, val end: String, val description: String? = null, val id: String? = null, val etag: String? = null)
private data class StoredGoogleToken(val accessToken: String, val refreshToken: String?, val expiresAt: String, val accountName: String, val reauthorizationRequired: Boolean = false)

interface GoogleOAuthClient {
    fun exchange(code: String, redirectUri: String, clientId: String, clientSecret: String): GoogleToken
    fun refresh(refreshToken: String, clientId: String, clientSecret: String, accountName: String): GoogleToken
    fun revoke(token: String)
    fun events(accessToken: String): GoogleCalendarEvents
    fun rangedEvents(accessToken: String, calendarId: String, start: String, end: String): GoogleCalendarEvents = events(accessToken)
    fun getEvent(accessToken: String, calendarId: String, eventId: String): GoogleCalendarEvent = throw UnsupportedOperationException()
    fun patchEvent(accessToken: String, eventId: String, body: GoogleCalendarEventRequest, etag: String): GoogleCalendarEvent = throw UnsupportedOperationException()
    fun removeEvent(accessToken: String, calendarId: String, eventId: String, etag: String): Unit = throw UnsupportedOperationException()
    fun calendars(accessToken: String): GoogleCalendars = throw UnsupportedOperationException()
    fun createEvent(accessToken: String, body: GoogleCalendarEventRequest): GoogleCalendarEvent = throw UnsupportedOperationException()
    fun updateEvent(accessToken: String, eventId: String, body: GoogleCalendarEventRequest): GoogleCalendarEvent = throw UnsupportedOperationException()
    fun deleteEvent(accessToken: String, eventId: String): Unit = throw UnsupportedOperationException()
}

@Service
class HttpGoogleOAuthClient(private val http: HttpClient = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build()) : GoogleOAuthClient {
    private val mapper = jacksonObjectMapper()
    private fun post(url: String, body: String, auth: String? = null): JsonNode {
        val builder = HttpRequest.newBuilder(URI(url)).timeout(Duration.ofSeconds(15)).header("Content-Type", "application/x-www-form-urlencoded").POST(HttpRequest.BodyPublishers.ofString(body)); if (auth != null) builder.header("Authorization", auth)
        val response = http.send(builder.build(), HttpResponse.BodyHandlers.ofString()); if (response.statusCode() !in 200..299) throw GoogleProviderException(response.statusCode(), response.headers()?.firstValue("Retry-After")?.orElse(null)?.toLongOrNull()?.coerceIn(0,86400)); return mapper.readTree(response.body())
    }
    override fun exchange(code: String, redirectUri: String, clientId: String, clientSecret: String): GoogleToken {
        val node = post("https://oauth2.googleapis.com/token", form(mapOf("code" to code, "client_id" to clientId, "client_secret" to clientSecret, "redirect_uri" to redirectUri, "grant_type" to "authorization_code")))
        val credentials = token(node, null)
        val identity = mapper.readTree(request("https://openidconnect.googleapis.com/v1/userinfo", "GET", credentials.accessToken, null))
        val account = identity.path("email").asText("")
        if (identity.path("sub").asText("").isBlank() || !identity.path("email_verified").asBoolean(false) || account.isBlank() || account.length > 160) throw GoogleProviderUnavailableException()
        return GoogleToken(credentials.accessToken, credentials.refreshToken, credentials.expiresAt, account)
    }
    override fun refresh(refreshToken: String, clientId: String, clientSecret: String, accountName: String): GoogleToken { val node = post("https://oauth2.googleapis.com/token", form(mapOf("refresh_token" to refreshToken, "client_id" to clientId, "client_secret" to clientSecret, "grant_type" to "refresh_token"))); val refreshed = token(node, accountName); return GoogleToken(refreshed.accessToken, refreshToken, refreshed.expiresAt, refreshed.accountName) }
    override fun revoke(token: String) { post("https://oauth2.googleapis.com/revoke?token=${enc(token)}", "") }
    override fun events(accessToken: String) = rangedEvents(accessToken, "primary", Instant.now().minus(Duration.ofDays(31)).toString(), Instant.now().plus(Duration.ofDays(366)).toString())
    override fun rangedEvents(accessToken: String, calendarId: String, start: String, end: String): GoogleCalendarEvents {
        val items = mutableListOf<GoogleCalendarEvent>()
        var page: String? = null
        val seen = mutableSetOf<String>()
        do {
            val url = "https://www.googleapis.com/calendar/v3/calendars/${enc(calendarId)}/events?singleEvents=true&orderBy=startTime&maxResults=250&timeMin=${enc(start)}&timeMax=${enc(end)}" + (page?.let { "&pageToken=${enc(it)}" } ?: "")
            val node = mapper.readTree(request(url, "GET", accessToken, null))
            items += node.path("items").filter { it.path("status").asText() != "cancelled" }.map { event(it.toString()) }
            page = node.path("nextPageToken").asText(null)
            if (items.size > 10000 || (page != null && !seen.add(page))) throw GoogleProviderUnavailableException()
        } while (page != null)
        return GoogleCalendarEvents(items)
    }
    override fun getEvent(accessToken: String, calendarId: String, eventId: String) = event(request("https://www.googleapis.com/calendar/v3/calendars/${enc(calendarId)}/events/${enc(eventId)}", "GET", accessToken, null))
    override fun patchEvent(accessToken: String, eventId: String, body: GoogleCalendarEventRequest, etag: String) = event(request("https://www.googleapis.com/calendar/v3/calendars/${enc(body.calendarId)}/events/${enc(eventId)}", "PATCH", accessToken, eventJson(body), etag))
    override fun removeEvent(accessToken: String, calendarId: String, eventId: String, etag: String) { request("https://www.googleapis.com/calendar/v3/calendars/${enc(calendarId)}/events/${enc(eventId)}", "DELETE", accessToken, null, etag) }
    override fun calendars(accessToken: String): GoogleCalendars {
        val items = mutableListOf<GoogleCalendar>()
        var page: String? = null
        val seen = mutableSetOf<String>()
        do {
            val node = mapper.readTree(request("https://www.googleapis.com/calendar/v3/users/me/calendarList?maxResults=250" + (page?.let { "&pageToken=${enc(it)}" } ?: ""), "GET", accessToken, null))
            items += node.path("items").map { GoogleCalendar(it.path("id").asText(), it.path("summary").asText("(untitled)"), it.path("timeZone").asText(null), it.path("accessRole").asText("reader"), it.path("primary").asBoolean(false)) }
            page = node.path("nextPageToken").asText(null)
            if (items.size > 1000 || (page != null && !seen.add(page))) throw GoogleProviderUnavailableException()
        } while (page != null)
        return GoogleCalendars(items)
    }
    override fun createEvent(accessToken: String, body: GoogleCalendarEventRequest): GoogleCalendarEvent = event(request("https://www.googleapis.com/calendar/v3/calendars/${enc(body.calendarId)}/events", "POST", accessToken, eventJson(body)))
    override fun updateEvent(accessToken: String, eventId: String, body: GoogleCalendarEventRequest): GoogleCalendarEvent = event(request("https://www.googleapis.com/calendar/v3/calendars/${enc(body.calendarId)}/events/${enc(eventId)}", "PUT", accessToken, eventJson(body)))
    override fun deleteEvent(accessToken: String, eventId: String) { request("https://www.googleapis.com/calendar/v3/calendars/primary/events/${enc(eventId)}", "DELETE", accessToken, null) }
    private fun request(url: String, method: String, accessToken: String, body: String?, etag: String? = null): String { val builder=HttpRequest.newBuilder(URI(url)).timeout(Duration.ofSeconds(15)).header("Authorization", "Bearer $accessToken"); if(etag!=null) builder.header("If-Match", etag); if(body!=null) builder.header("Content-Type", "application/json"); val request=when(method){"POST"->builder.POST(HttpRequest.BodyPublishers.ofString(body!!)).build();"PATCH"->builder.method("PATCH", HttpRequest.BodyPublishers.ofString(body!!)).build();"PUT"->builder.PUT(HttpRequest.BodyPublishers.ofString(body!!)).build();"DELETE"->builder.DELETE().build();else->builder.GET().build()}; val response=http.send(request,HttpResponse.BodyHandlers.ofString()); if(response.statusCode() !in 200..299) throw GoogleProviderException(response.statusCode(), response.headers()?.firstValue("Retry-After")?.orElse(null)?.toLongOrNull()?.coerceIn(0,86400)); return response.body() }
    private fun eventJson(body: GoogleCalendarEventRequest)=mapper.createObjectNode().apply { put("summary",body.summary); if(body.id != null) { put("id",body.id); set<JsonNode>("extendedProperties", mapper.createObjectNode().set<JsonNode>("private", mapper.createObjectNode().put("kyrionId",body.id))) }; put("description",body.description ?: ""); set<JsonNode>("start",mapper.createObjectNode().put("dateTime",body.start)); set<JsonNode>("end",mapper.createObjectNode().put("dateTime",body.end)) }.toString()
    private fun event(body: String)=mapper.readTree(body).let {
        GoogleCalendarEvent(it.path("id").asText(), it.path("summary").asText("(untitled)"),
            it.path("start").path("dateTime").asText(null) ?: it.path("start").path("date").asText(null),
            it.path("end").path("dateTime").asText(null) ?: it.path("end").path("date").asText(null),
            it.path("etag").asText(null), it.path("status").asText("confirmed"), it.path("description").asText(null),
            it.has("recurrence") || it.has("recurringEventId"), it.path("extendedProperties").path("private").path("kyrionId").asText(null))
    }
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
    private val random = SecureRandom(); private val pending = ConcurrentHashMap<String, Pair<UUID, Instant>>(); private val mapper = jacksonObjectMapper().findAndRegisterModules()
    fun configured() = clientId.isNotBlank() && clientSecret.isNotBlank() && redirectUri.isNotBlank()
    fun status(ownerId: UUID): GoogleStatus { val connection = connection(ownerId) ?: return GoogleStatus(configured(), false); val enabled = grants.findAll(ownerId, connection.id).any { it.capability == CALENDAR_READ && it.granted }; return GoogleStatus(configured(), true, connection.displayName, !enabled || stored(connection).reauthorizationRequired) }
    fun authorize(ownerId: UUID): GoogleAuthorization { if (!configured()) throw GoogleNotConfiguredException(); val bytes = ByteArray(32).also(random::nextBytes); val state = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes); pending[state] = ownerId to clock.instant().plusSeconds(600); val query = mapOf("client_id" to clientId, "redirect_uri" to redirectUri, "response_type" to "code", "scope" to "openid email profile $GOOGLE_CALENDAR_SCOPE", "access_type" to "offline", "prompt" to "consent", "state" to state).entries.joinToString("&") { "${enc(it.key)}=${enc(it.value)}" }; return GoogleAuthorization("https://accounts.google.com/o/oauth2/v2/auth?$query") }
    fun complete(ownerId: UUID, code: String, state: String): GoogleStatus { val request = pending[state] ?: throw GoogleInvalidStateException(); if (request.first != ownerId || request.second.isBefore(clock.instant()) || !pending.remove(state, request)) throw GoogleInvalidStateException(); val token = client.exchange(code, redirectUri, clientId, clientSecret); val now = clock.instant(); val accounts = repository.findAll(ownerId).filter { it.provider == GOOGLE_PROVIDER }; if(accounts.size > 1 || accounts.singleOrNull()?.let { it.displayName != token.accountName && it.displayName != "Google account" } == true) throw GoogleDifferentAccountException(); val existing = accounts.singleOrNull(); val id = existing?.id ?: UUID.randomUUID(); val payload = mapper.writeValueAsString(StoredGoogleToken(token.accessToken, token.refreshToken, token.expiresAt.toString(), token.accountName)); val protected = cipher.protect(payload, "$ownerId:$id:$GOOGLE_PROVIDER"); if (existing == null) repository.save(IntegrationConnection(id, ownerId, GOOGLE_PROVIDER, token.accountName, token.accountName, protected.ciphertext, protected.nonce, protected.version, now, now)) else { repository.updateCredential(ownerId, id, protected, now); if(existing.displayName != token.accountName) repository.rename(ownerId,id,token.accountName,now) }; grants.replace(ownerId, id, setOf(CALENDAR_READ, CALENDAR_EVENT_CREATE, CALENDAR_EVENT_UPDATE, CALENDAR_EVENT_DELETE), now); return GoogleStatus(true, true, token.accountName) }
    fun events(ownerId: UUID, calendarId: String = "primary", start: String? = null, end: String? = null): GoogleCalendarEvents {
        val from = start?.let { parseInstant(it) } ?: clock.instant().minus(Duration.ofDays(31))
        val until = end?.let { parseInstant(it) } ?: clock.instant().plus(Duration.ofDays(366))
        if (!until.isAfter(from) || Duration.between(from, until) > Duration.ofDays(400)) throw GoogleInvalidRequestException()
        return withToken(ownerId, CALENDAR_READ) { client.rangedEvents(it, calendarId, from.toString(), until.toString()) }
    }
    private fun parseInstant(value: String): Instant = try { Instant.parse(value) } catch (_: Exception) { throw GoogleInvalidRequestException() }
    fun remoteEvent(ownerId: UUID, calendarId: String, eventId: String) = withToken(ownerId, CALENDAR_READ) { client.getEvent(it, calendarId, eventId) }
    fun patchEvent(ownerId: UUID, eventId: String, body: GoogleCalendarEventRequest, etag: String): GoogleCalendarEvent {
        requireWritableRemote(remoteEvent(ownerId,body.calendarId,eventId),etag)
        return withToken(ownerId, CALENDAR_EVENT_UPDATE) { client.patchEvent(it, eventId, body, etag) }
    }
    fun removeEvent(ownerId: UUID, calendarId: String, eventId: String, etag: String) {
        requireWritableRemote(remoteEvent(ownerId,calendarId,eventId),etag)
        withToken(ownerId, CALENDAR_EVENT_DELETE) { client.removeEvent(it, calendarId, eventId, etag) }
    }
    private fun requireWritableRemote(event: GoogleCalendarEvent, etag: String) {
        if(event.recurring || event.start == null || event.end == null || event.start.length == 10 || event.end.length == 10) throw GoogleReadOnlyEventException()
        if(event.etag != etag) throw GoogleProviderException(412)
    }
    fun calendars(ownerId: UUID) = withToken(ownerId, CALENDAR_READ) { client.calendars(it) }
    fun createEvent(ownerId: UUID, body: GoogleCalendarEventRequest): GoogleCalendarEvent {
        validateEvent(body)
        return withToken(ownerId, CALENDAR_EVENT_CREATE) { client.createEvent(it, body) }
    }
    fun updateEvent(ownerId: UUID, eventId: String, body: GoogleCalendarEventRequest): GoogleCalendarEvent {
        validateEvent(body)
        val etag = body.etag?.takeIf { it.isNotBlank() && it.length <= 512 && !it.contains('\n') && !it.contains('\r') } ?: throw GoogleInvalidRequestException()
        return patchEvent(ownerId, eventId, body, etag)
    }
    fun deleteEvent(ownerId: UUID, eventId: String, calendarId: String, etag: String) {
        if (calendarId.isBlank() || calendarId.length > 512 || etag.isBlank() || etag.length > 512 || etag.any { it == '\n' || it == '\r' }) throw GoogleInvalidRequestException()
        removeEvent(ownerId, calendarId, eventId, etag)
    }
    private fun validateEvent(body: GoogleCalendarEventRequest) {
        if (body.summary.isBlank() || body.summary.length > 500 || (body.description?.length ?: 0) > 10000 || body.calendarId.isBlank() || body.calendarId.length > 512) throw GoogleInvalidRequestException()
        if (!parseInstant(body.end).isAfter(parseInstant(body.start))) throw GoogleInvalidRequestException()
    }
    @Synchronized
    private fun <T> withToken(ownerId: UUID, capability: String, action: (String) -> T): T {
        val connection = connection(ownerId) ?: throw GoogleDisconnectedException()
        if (!grants.findAll(ownerId, connection.id).any { it.capability == capability && it.granted }) throw GoogleCapabilityDisabledException()
        if (stored(connection).reauthorizationRequired) throw GoogleReauthorizationException()
        var current = token(connection)
        fun refresh(): GoogleToken {
            val refresh = current.refreshToken ?: run { markReauthorization(connection); throw GoogleReauthorizationException() }
            val next = try { client.refresh(refresh, clientId, clientSecret, current.accountName) }
                catch (error: GoogleProviderException) { if(error.status in setOf(400,401)) { markReauthorization(connection); throw GoogleReauthorizationException() }; throw error }
            return GoogleToken(next.accessToken, next.refreshToken ?: refresh, next.expiresAt, next.accountName).also { saveToken(connection, it) }
        }
        if (!current.expiresAt.isAfter(clock.instant().plusSeconds(30))) current = refresh()
        return try { action(current.accessToken) } catch (error: GoogleProviderException) {
            if (error.status != 401) throw error
            current = refresh()
            try { action(current.accessToken) } catch (retry: GoogleProviderException) {
                if (retry.status == 401) { markReauthorization(connection); throw GoogleReauthorizationException() }
                throw retry
            }
        }
    }
    fun disconnect(ownerId: UUID) { val connection = connection(ownerId) ?: return; runCatching { client.revoke(token(connection).accessToken) }; grants.delete(ownerId, connection.id); repository.delete(ownerId, connection.id) }
    private fun connection(ownerId: UUID) = repository.findAll(ownerId).firstOrNull { it.provider == GOOGLE_PROVIDER }
    private fun stored(connection: IntegrationConnection) = mapper.readValue(cipher.reveal(connection), StoredGoogleToken::class.java)
    private fun markReauthorization(connection: IntegrationConnection) {
        val value = stored(connection).copy(reauthorizationRequired = true)
        val protected = cipher.protect(mapper.writeValueAsString(value), "${connection.ownerId}:${connection.id}:$GOOGLE_PROVIDER")
        repository.updateCredential(connection.ownerId, connection.id, protected, clock.instant())
    }
    private fun token(connection: IntegrationConnection): GoogleToken { val value = mapper.readValue(cipher.reveal(connection), StoredGoogleToken::class.java); return GoogleToken(value.accessToken, value.refreshToken, Instant.parse(value.expiresAt), value.accountName) }
    private fun saveToken(connection: IntegrationConnection, token: GoogleToken) { val value = StoredGoogleToken(token.accessToken, token.refreshToken, token.expiresAt.toString(), token.accountName); val protected = cipher.protect(mapper.writeValueAsString(value), "${connection.ownerId}:${connection.id}:$GOOGLE_PROVIDER"); repository.updateCredential(connection.ownerId, connection.id, protected, clock.instant()) }
    private fun enc(value: String) = URLEncoder.encode(value, StandardCharsets.UTF_8)
}

@RestController
@RequestMapping("/v1/integrations/google")
class GoogleIntegrationController(private val service: GoogleIntegrationService, private val activity: ActivityService) {
    @GetMapping fun status(request: HttpServletRequest) = service.status(request.authenticatedUserId())
    @PostMapping("/authorization") fun authorize(request: HttpServletRequest) = service.authorize(request.authenticatedUserId())
    @PostMapping("/authorization/complete") fun complete(@RequestBody body: Map<String, String>, request: HttpServletRequest) = service.complete(request.authenticatedUserId(), body["code"] ?: throw GoogleInvalidRequestException(), body["state"] ?: throw GoogleInvalidRequestException())
    @GetMapping("/calendar/events") fun events(request: HttpServletRequest, @RequestParam(defaultValue = "primary") calendarId: String, @RequestParam(required = false) start: String?, @RequestParam(required = false) end: String?) = service.events(request.authenticatedUserId(), calendarId, start, end)
    @GetMapping("/calendar/calendars") fun calendars(request: HttpServletRequest) = service.calendars(request.authenticatedUserId())
    @PostMapping("/calendar/events") fun create(@RequestBody body: GoogleCalendarEventRequest, request: HttpServletRequest) = audited(request, "google.calendar.event.created") { service.createEvent(request.authenticatedUserId(), body) }
    @PutMapping("/calendar/events/{eventId}") fun update(@PathVariable eventId: String, @RequestBody body: GoogleCalendarEventRequest, request: HttpServletRequest) = audited(request, "google.calendar.event.updated") { service.updateEvent(request.authenticatedUserId(), eventId, body) }
    @DeleteMapping("/calendar/events/{eventId}") @ResponseStatus(HttpStatus.NO_CONTENT) fun delete(@PathVariable eventId: String, @RequestParam calendarId: String, @RequestParam etag: String, request: HttpServletRequest) = audited(request, "google.calendar.event.deleted") { service.deleteEvent(request.authenticatedUserId(), eventId, calendarId, etag) }
    @DeleteMapping @ResponseStatus(HttpStatus.NO_CONTENT) fun disconnect(request: HttpServletRequest) = service.disconnect(request.authenticatedUserId())
    private fun <T> audited(request: HttpServletRequest, type: String, action: () -> T): T {
        val actor = request.authenticatedUserId()
        val correlation = UUID.randomUUID()
        fun record(status: ActivityStatus) = activity.record(ActivityCategory.INTEGRATION, type, status,
            ActivityActorType.USER, "kyrion-core", type, actor.toString(), correlation, actor)
        // Persist intent before contacting the provider; do not hold a DB transaction across HTTP.
        record(ActivityStatus.PROPOSED)
        val result = try { action() } catch (error: Exception) {
            record(ActivityStatus.FAILED)
            throw error
        }
        record(ActivityStatus.SUCCEEDED)
        return result
    }

}

class GoogleNotConfiguredException : RuntimeException(); class GoogleInvalidStateException : RuntimeException(); class GoogleInvalidRequestException : RuntimeException(); class GoogleDisconnectedException : RuntimeException(); class GoogleCapabilityDisabledException : RuntimeException(); class GoogleProviderUnavailableException : RuntimeException(); class GoogleProviderException(val status: Int, val retryAfterSeconds: Long? = null) : RuntimeException()


@RestControllerAdvice
class GoogleErrorHandler {
    @ExceptionHandler(GoogleReadOnlyEventException::class)
    @ResponseStatus(HttpStatus.FORBIDDEN)
    fun readOnly() = mapOf("code" to "GOOGLE_EVENT_READ_ONLY")
    @ExceptionHandler(GoogleInvalidRequestException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = mapOf("code" to "GOOGLE_REQUEST_INVALID")
    @ExceptionHandler(GoogleDifferentAccountException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun differentAccount() = mapOf("code" to "GOOGLE_ACCOUNT_CHANGE_REQUIRES_DISCONNECT")
    @ExceptionHandler(GoogleReauthorizationException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun reauthorize() = mapOf("code" to "GOOGLE_REAUTHORIZATION_REQUIRED")
    @ExceptionHandler(GoogleProviderException::class, GoogleProviderUnavailableException::class)
    @ResponseStatus(HttpStatus.BAD_GATEWAY)
    fun unavailable(error: Exception): org.springframework.http.ResponseEntity<Map<String,String>> {
        val conflict = error is GoogleProviderException && error.status in setOf(404,409,410,412)
        return org.springframework.http.ResponseEntity.status(if(conflict) 409 else 502).body(mapOf("code" to if(conflict) "CALENDAR_SYNC_CONFLICT" else "GOOGLE_UNAVAILABLE"))
    }
    @ExceptionHandler(GoogleDisconnectedException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun disconnected() = mapOf("code" to "GOOGLE_DISCONNECTED")
    @ExceptionHandler(GoogleCapabilityDisabledException::class)
    @ResponseStatus(HttpStatus.FORBIDDEN)
    fun disabled() = mapOf("code" to "GOOGLE_CAPABILITY_DISABLED")
}

class GoogleReauthorizationException : RuntimeException()
class GoogleDifferentAccountException : RuntimeException()
class GoogleReadOnlyEventException : RuntimeException()
