package dev.kyrion.core.activity

import dev.kyrion.core.security.AUTHENTICATED_USER_ID_ATTRIBUTE
import dev.kyrion.core.security.UnauthenticatedException
import jakarta.servlet.http.HttpServletRequest
import jakarta.validation.constraints.Max
import jakarta.validation.constraints.Min
import org.springframework.validation.annotation.Validated
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

data class ActivityResponse(val items: List<ActivityEvent>)
data class ActivityIntegrityResponse(val owner: ActivityIntegrityChainReport, val system: ActivityIntegrityChainReport)

@Validated
@RestController
@RequestMapping("/v1/activity")
class ActivityController(
    private val activityService: ActivityService,
    private val integrityVerifier: ActivityIntegrityVerifier,
) {
    @GetMapping
    fun recent(
        @RequestParam(defaultValue = "50")
        @Min(1)
        @Max(100)
        limit: Int,
        request: HttpServletRequest,
    ): ActivityResponse = ActivityResponse(activityService.recent(request.ownerId(), limit))

    @GetMapping("/integrity")
    fun integrity(request: HttpServletRequest): ActivityIntegrityResponse {
        val ownerId = request.ownerId()
        return ActivityIntegrityResponse(integrityVerifier.verify(ownerId.toString()), integrityVerifier.verify(SYSTEM_SCOPE))
    }

    private fun HttpServletRequest.ownerId() =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? java.util.UUID ?: throw UnauthenticatedException()
}
