package dev.kyrion.core.security

import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.Valid
import jakarta.validation.constraints.Size
import org.springframework.http.HttpStatus
import org.springframework.web.bind.annotation.*

data class EmailAddressRequest(@field:Size(min = 3, max = 254) val email: String)

data class EmailProofRequest(@field:Size(min = 43, max = 43) val code: String)

data class DomainRequest(@field:Size(min = 3, max = 253) val domain: String)

data class RegistrationEmailRequest(
    @field:Size(max = 43) val invitationCode: String,
    @field:Size(max = 254) val email: String,
)

@RestController
@RequestMapping("/v1/identity")
class BusinessIdentityController(private val identities: BusinessIdentityService) {
    @GetMapping("/email")
    fun email(request: HttpServletRequest) = identities.email(request.authenticatedUserId())

    @PostMapping("/email")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun requestEmail(@Valid @RequestBody body: EmailAddressRequest, request: HttpServletRequest) =
        identities.requestEmail(request.authenticatedUserId(), body.email)

    @PostMapping("/email/verify")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    fun verify(@Valid @RequestBody body: EmailProofRequest, request: HttpServletRequest) =
        identities.verifyEmail(request.authenticatedUserId(), body.code)

    @GetMapping("/business")
    fun policy(request: HttpServletRequest) = identities.policy(request.authenticatedUserId())

    @PutMapping("/business")
    fun policy(@RequestBody body: BusinessPolicyRequest, request: HttpServletRequest) =
        identities.updatePolicy(request.authenticatedUserId(), body)

    @PostMapping("/business/challenge")
    fun challenge(@Valid @RequestBody body: DomainRequest, request: HttpServletRequest) =
        identities.challengeDomain(request.authenticatedUserId(), body.domain)

    @PostMapping("/business/verify")
    fun verifyDomain(@Valid @RequestBody body: DomainRequest, request: HttpServletRequest) =
        identities.verifyDomain(request.authenticatedUserId(), body.domain)

    @PostMapping("/business/suspend")
    fun suspendDomain(@Valid @RequestBody body: DomainRequest, request: HttpServletRequest) =
        identities.suspendDomain(request.authenticatedUserId(), body.domain)
}

@RestController
class RegistrationEmailController(private val identities: BusinessIdentityService) {
    @PostMapping("/v1/auth/registration-email")
    @ResponseStatus(HttpStatus.ACCEPTED)
    fun request(@Valid @RequestBody body: RegistrationEmailRequest) {
        try {
            identities.requestRegistrationEmail(body.invitationCode, body.email)
        } catch (_: IdentityPolicyException) {
            /* Identical response; never expose invitation/account state. */
        }
    }
}

@RestControllerAdvice
class BusinessIdentityErrors {
    @ExceptionHandler(IdentityPolicyException::class)
    @ResponseStatus(HttpStatus.BAD_REQUEST)
    fun identity(exception: IdentityPolicyException) = ErrorResponse(exception.code)
}
