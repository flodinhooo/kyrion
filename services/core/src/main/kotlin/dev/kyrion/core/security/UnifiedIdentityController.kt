package dev.kyrion.core.security

import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import jakarta.validation.Valid
import jakarta.validation.constraints.Pattern
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.annotation.*

data class CentralStartRequest(@field:Pattern(regexp = "LOGIN|LINK") val mode: String, @field:Size(max = 200) val currentPassword: String? = null)
data class CentralOperationRequest(@field:Pattern(regexp = "[A-Za-z0-9_-]{43}") val operationToken: String, val confirm: Boolean = false)
data class CentralUnlinkRequest(@field:Size(min = 12, max = 200) val currentPassword: String)

@RestController
@RequestMapping("/v1/auth/central")
class UnifiedIdentityController(private val identities: UnifiedIdentityService, private val rbac: RbacService) {
    @ModelAttribute fun noStore(response: HttpServletResponse) { response.setHeader("Cache-Control", "no-store") }
    @GetMapping("/config") fun config() = mapOf("enabled" to identities.available())
    @GetMapping("/status") fun status(request: HttpServletRequest) = identities.status(request.sessionToken() ?: throw UnauthenticatedException())
    @PostMapping("/start") fun start(@Valid @RequestBody body: CentralStartRequest, request: HttpServletRequest) = identities.start(body.mode, request.sessionToken(), body.currentPassword)
    @PostMapping("/poll") fun poll(@Valid @RequestBody body: CentralOperationRequest, request: HttpServletRequest) = identities.poll(body.operationToken, request.sessionToken())
    @PostMapping("/complete") fun complete(@Valid @RequestBody body: CentralOperationRequest, request: HttpServletRequest): Any {
        val result = identities.complete(body.operationToken, request.sessionToken(), body.confirm) ?: return mapOf("linked" to true)
        return SessionResponse(UserResponse(result.user.id, result.user.username, "invitations:create" in rbac.permissions(result.user.id)), result.session.rawToken, result.session.session.expiresAt)
    }
    @PostMapping("/cancel") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun cancel(@Valid @RequestBody body: CentralOperationRequest, request: HttpServletRequest) = identities.cancel(body.operationToken, request.sessionToken())
    @DeleteMapping("/link") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun unlink(@Valid @RequestBody body: CentralUnlinkRequest, request: HttpServletRequest) = identities.unlink(request.sessionToken() ?: throw UnauthenticatedException(), body.currentPassword)
    private fun HttpServletRequest.sessionToken() = getHeader("Authorization")?.takeIf { it.startsWith("Bearer ") }?.substring(7)
}

@RestControllerAdvice
class UnifiedIdentityErrorHandler {
    @ExceptionHandler(CentralIdentityException::class)
    fun error(error: CentralIdentityException): ResponseEntity<ErrorResponse> = ResponseEntity.status(when(error.code) {
        "CENTRAL_DISABLED" -> 404
        "CENTRAL_UNAVAILABLE" -> 503
        "SPACE_ACCESS_REQUIRED", "CENTRAL_DENIED", "LOCAL_LOGIN_REQUIRED" -> 403
        "CENTRAL_IDENTITY_ALREADY_LINKED" -> 409
        else -> 400
    }).header("Cache-Control", "no-store").body(ErrorResponse(error.code))
}
