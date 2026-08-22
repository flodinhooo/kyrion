package dev.kyrion.core.security

import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.NotBlank
import jakarta.validation.constraints.Pattern
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.http.ResponseEntity
import org.springframework.web.bind.MethodArgumentNotValidException
import org.springframework.http.converter.HttpMessageNotReadableException
import org.springframework.web.bind.annotation.ExceptionHandler
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.DeleteMapping
import org.springframework.web.bind.annotation.PathVariable
import org.springframework.web.bind.annotation.PostMapping
import org.springframework.web.bind.annotation.RequestBody
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.ResponseStatus
import org.springframework.web.bind.annotation.RestController
import org.springframework.web.bind.annotation.RestControllerAdvice
import java.time.Instant
import java.util.UUID

data class CredentialsRequest(
    @field:NotBlank @field:Size(min = 3, max = 120)
    @field:Pattern(regexp = "^[A-Za-z0-9._-]+$") val username: String,
    @field:Size(min = 12, max = 200) val password: String,
)
data class SetupStatusResponse(val setupRequired: Boolean)
data class ChangePasswordRequest(
    @field:Size(min = 12, max = 200) val currentPassword: String,
    @field:Size(min = 12, max = 200) val newPassword: String,
)
data class UserResponse(val id: UUID, val username: String)
data class SessionResponse(val user: UserResponse, val sessionToken: String, val expiresAt: Instant)
data class ErrorResponse(val code: String)

@RestController
@RequestMapping("/v1/auth")
class AuthenticationController(private val authentication: LocalAuthenticationService) {
    @GetMapping("/setup/status") fun setupStatus() = SetupStatusResponse(authentication.setupRequired())

    @PostMapping("/setup") @ResponseStatus(HttpStatus.CREATED)
    fun setup(@Valid @RequestBody body: CredentialsRequest) = authentication.setup(body.username, body.password).response()

    @PostMapping("/login")
    fun login(@Valid @RequestBody body: CredentialsRequest) = authentication.login(body.username, body.password).response()

    @GetMapping("/me")
    fun me(request: HttpServletRequest): UserResponse {
        val user = authentication.authenticate(request.bearerToken()) ?: throw UnauthenticatedException()
        return UserResponse(user.id, user.username)
    }

    @PostMapping("/logout") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun logout(request: HttpServletRequest) {
        val token = request.bearerToken()
        val user = authentication.authenticate(token) ?: throw UnauthenticatedException()
        authentication.logout(token, user.id)
    }

    @PostMapping("/password")
    fun changePassword(@Valid @RequestBody body: ChangePasswordRequest, request: HttpServletRequest): SessionResponse =
        authentication.changePassword(request.bearerToken(), body.currentPassword, body.newPassword).response()

    @GetMapping("/sessions")
    fun sessions(request: HttpServletRequest) = authentication.activeSessions(request.bearerToken())

    @DeleteMapping("/sessions/{sessionId}") @ResponseStatus(HttpStatus.NO_CONTENT)
    fun revokeSession(@PathVariable sessionId: UUID, request: HttpServletRequest) {
        authentication.revokeSession(request.bearerToken(), sessionId)
    }

    private fun AuthenticatedOwner.response() = SessionResponse(
        UserResponse(user.id, user.username), session.rawToken, session.session.expiresAt,
    )
}

private fun HttpServletRequest.bearerToken(): String {
    val value = getHeader("Authorization") ?: throw UnauthenticatedException()
    if (!value.startsWith("Bearer ") || value.length <= 7) throw UnauthenticatedException()
    return value.substring(7)
}

class UnauthenticatedException : RuntimeException()

@RestControllerAdvice
class AuthenticationErrorHandler {
    @ExceptionHandler(SetupAlreadyCompletedException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun setupComplete() = ErrorResponse("SETUP_ALREADY_COMPLETED")

    @ExceptionHandler(InvalidCredentialsException::class, UnauthenticatedException::class)
    @ResponseStatus(HttpStatus.UNAUTHORIZED)
    fun unauthorized() = ErrorResponse("UNAUTHENTICATED")

    @ExceptionHandler(LoginRateLimitedException::class)
    fun loginRateLimited(exception: LoginRateLimitedException): ResponseEntity<ErrorResponse> {
        val retryAfterSeconds = exception.retryAfter.seconds.coerceAtLeast(1)
        return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
            .header("Retry-After", retryAfterSeconds.toString())
            .body(ErrorResponse("LOGIN_RATE_LIMITED"))
    }

    @ExceptionHandler(InvalidCurrentPasswordException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalidCurrentPassword() = ErrorResponse("INVALID_CURRENT_PASSWORD")

    @ExceptionHandler(PasswordUnchangedException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun passwordUnchanged() = ErrorResponse("PASSWORD_UNCHANGED")

    @ExceptionHandler(AuthSessionNotFoundException::class)
    @ResponseStatus(HttpStatus.NOT_FOUND)
    fun sessionNotFound() = ErrorResponse("AUTH_SESSION_NOT_FOUND")

    @ExceptionHandler(CurrentSessionRevocationException::class)
    @ResponseStatus(HttpStatus.CONFLICT)
    fun currentSessionRevocation() = ErrorResponse("CURRENT_SESSION_REQUIRES_LOGOUT")

    @ExceptionHandler(MethodArgumentNotValidException::class, HttpMessageNotReadableException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun invalid() = ErrorResponse("INVALID_REQUEST")
}
