package dev.kyrion.core.activity

import org.springframework.boot.ApplicationArguments
import org.springframework.boot.ApplicationRunner
import org.springframework.stereotype.Component

@Component
class CoreStartupActivity(
    private val activityService: ActivityService,
) : ApplicationRunner {
    override fun run(args: ApplicationArguments) {
        activityService.record(
            category = ActivityCategory.SYSTEM,
            eventType = "core.started",
            status = ActivityStatus.SUCCEEDED,
            actorType = ActivityActorType.SYSTEM,
            source = "kyrion-core",
            summaryCode = "activity.core.started",
        )
    }
}
