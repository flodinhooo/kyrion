package dev.kyrion.core.activity

import jakarta.validation.constraints.Max
import jakarta.validation.constraints.Min
import org.springframework.validation.annotation.Validated
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RequestParam
import org.springframework.web.bind.annotation.RequestMapping
import org.springframework.web.bind.annotation.RestController

data class ActivityResponse(val items: List<ActivityEvent>)

@Validated
@RestController
@RequestMapping("/v1/activity")
class ActivityController(
    private val activityService: ActivityService,
) {
    @GetMapping
    fun recent(
        @RequestParam(defaultValue = "50")
        @Min(1)
        @Max(100)
        limit: Int,
    ): ActivityResponse = ActivityResponse(activityService.recent(limit))
}
