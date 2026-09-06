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
data class ActionTimelineResponse(val items: List<ActivityEvent>, val truncated: Boolean, val outcome: dev.kyrion.core.action.ActionOutcome? = null)
data class ActivityIntegrityResponse(val owner: ActivityIntegrityChainReport, val system: ActivityIntegrityChainReport)

@Validated
@RestController
@RequestMapping("/v1/activity")
class ActivityController(
    private val activityService: ActivityService,
    private val integrityVerifier: ActivityIntegrityVerifier,
    private val executions: dev.kyrion.core.action.ActionExecutionRepository? = null,
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

    @GetMapping("/timeline/{correlationId}")
    fun timeline(@org.springframework.web.bind.annotation.PathVariable correlationId: java.util.UUID, request: HttpServletRequest): ActionTimelineResponse {
        val events = activityService.timeline(request.ownerId(), correlationId)
        return ActionTimelineResponse(events.take(1000), events.size > 1000, executions?.outcome(request.ownerId(), correlationId))
    }

    private fun HttpServletRequest.ownerId() =
        getAttribute(AUTHENTICATED_USER_ID_ATTRIBUTE) as? java.util.UUID ?: throw UnauthenticatedException()
}
