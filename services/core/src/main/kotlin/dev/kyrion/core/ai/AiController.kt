package dev.kyrion.core.ai

import dev.kyrion.core.security.authenticatedUserId
import dev.kyrion.core.security.RbacService
import jakarta.servlet.http.HttpServletRequest
import org.springframework.http.MediaType
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody

@RestController
@RequestMapping("/v1/ai")
class AiController(
    private val settings: AiSettingsService, private val usage: AiUsageService,
    private val orchestration: AiOrchestrationService, private val rbac: RbacService,
    private val authentication: dev.kyrion.core.security.LocalAuthenticationService
) {
    @GetMapping("/preferences")
    fun preferences(request: HttpServletRequest): Map<String, Any> {
        val actor = request.authenticatedUserId()
        return mapOf(
            "preferences" to settings.preferences(actor), "policy" to settings.effectivePolicy(actor),
            "canAdmin" to ("system_settings:update" in rbac.permissions(actor))
        )
    }

    @PutMapping("/preferences")
    fun savePreferences(@RequestBody body: String, request: HttpServletRequest) =
        settings.savePreferences(request.authenticatedUserId(), parse(body, AiPreferences::class.java))

    @GetMapping("/policy")
    fun policy(request: HttpServletRequest) = settings.policy(request.authenticatedUserId())
    @PutMapping("/policy")
    fun savePolicy(@RequestBody body: String, request: HttpServletRequest) =
        settings.savePolicy(request.authenticatedUserId(), parse(body, AiPolicy::class.java))

    @GetMapping("/usage")
    fun usage(request: HttpServletRequest) = usage.summary(request.authenticatedUserId())
    @PostMapping("/route")
    fun route(@RequestBody body: String, request: HttpServletRequest) =
        orchestration.route(request.authenticatedUserId(), parse(body, AiRouteRequest::class.java))

    @PostMapping("/chat/stream", produces = ["application/x-ndjson"])
    fun stream(@RequestBody body: String, request: HttpServletRequest): ResponseEntity<StreamingResponseBody> {
        val actor = request.authenticatedUserId()
        val token = request.getHeader("Authorization")?.removePrefix("Bearer ") ?: throw dev.kyrion.core.security.UnauthenticatedException()
        val prepared =
            orchestration.prepare(request.authenticatedUserId(), parse(body, AiGenerationRequest::class.java))
        org.springframework.web.context.request.async.WebAsyncUtils.getAsyncManager(request)
            .asyncWebRequest?.setTimeout((prepared.timeoutSeconds + 10L) * 1000)
        return ResponseEntity.ok().contentType(MediaType.parseMediaType("application/x-ndjson"))
            .header("Cache-Control", "no-store").body(StreamingResponseBody { output ->
                orchestration.stream(prepared, {
                    if (authentication.authenticate(token)?.id != actor) throw dev.kyrion.core.security.UnauthenticatedException()
                }) { line ->
                    if (authentication.authenticate(token)?.id != actor) throw dev.kyrion.core.security.UnauthenticatedException()
                    output.write((line + "\n").toByteArray(Charsets.UTF_8)); output.flush() }
            })
    }

    private fun <T> parse(raw: String, type: Class<T>): T {
        if (raw.length > 64000) throw AiFailure("INVALID_REQUEST")
        return try {
            strictAiJson.readValue(raw, type)
        } catch (_: Exception) {
            throw AiFailure("INVALID_REQUEST")
        }
    }
}

@RestControllerAdvice
class AiErrorHandler {
    @ExceptionHandler(AiFailure::class)
    fun failure(error: AiFailure) = ResponseEntity.status(error.httpStatus).body(mapOf("code" to error.code))
}
