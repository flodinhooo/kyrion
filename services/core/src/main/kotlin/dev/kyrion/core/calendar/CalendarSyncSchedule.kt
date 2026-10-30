package dev.kyrion.core.calendar

import dev.kyrion.core.integration.*
import dev.kyrion.core.security.*
import dev.kyrion.core.activity.*
import jakarta.servlet.http.HttpServletRequest
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Service
import org.springframework.stereotype.Repository
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty
import org.springframework.web.bind.annotation.*
import org.springframework.http.HttpStatus
import java.time.Clock
import java.time.Instant
import java.sql.Timestamp
import java.util.UUID

data class CalendarSchedule(val enabled: Boolean = false, val intervalSeconds: Int = 300,
    val nextAttemptAt: Instant? = null, val lastAttemptAt: Instant? = null, val lastSuccessAt: Instant? = null,
    val failureCount: Int = 0, val lastError: String? = null, val running: Boolean = false)
data class CalendarScheduleRequest(
    @field:tools.jackson.databind.annotation.JsonDeserialize(using = CalendarBooleanDeserializer::class)
    val enabled: Boolean, val intervalSeconds: Int)

internal fun calendarRetrySeconds(failures: Int, retryAfter: Long? = null): Long =
    maxOf((60L shl (failures - 1).coerceIn(0, 6)).coerceAtMost(3600), retryAfter?.coerceIn(0, 86400) ?: 0)

@Repository
class CalendarScheduleRepository(private val jdbc: JdbcClient, private val clock: Clock = Clock.systemUTC()) {
    fun get(actor: UUID): CalendarSchedule = jdbc.sql("SELECT * FROM calendar_sync_schedule WHERE actor_id=:actor")
        .param("actor",actor).query { rs, _ -> CalendarSchedule(rs.getBoolean("enabled"),rs.getInt("interval_seconds"),
            rs.getTimestamp("next_attempt_at")?.toInstant(),rs.getTimestamp("last_attempt_at")?.toInstant(),
            rs.getTimestamp("last_success_at")?.toInstant(),rs.getInt("failure_count"),rs.getString("last_error"),
            rs.getTimestamp("lease_until")?.toInstant()?.isAfter(clock.instant()) == true) }.optional().orElse(CalendarSchedule())
    fun configure(actor: UUID, body: CalendarScheduleRequest) {
        jdbc.sql("""INSERT INTO calendar_sync_schedule(actor_id,enabled,interval_seconds) VALUES(:actor,:enabled,:interval)
            ON CONFLICT(actor_id) DO UPDATE SET enabled=EXCLUDED.enabled,interval_seconds=EXCLUDED.interval_seconds""")
            .param("actor",actor).param("enabled",body.enabled).param("interval",body.intervalSeconds).update()
    }
    fun suspend(actor: UUID) { jdbc.sql("UPDATE calendar_sync_schedule SET enabled=FALSE,last_error='FORBIDDEN' WHERE actor_id=:actor").param("actor",actor).update() }
    fun due(): List<UUID> = jdbc.sql("SELECT actor_id FROM calendar_sync_schedule WHERE enabled=TRUE AND next_attempt_at<=CURRENT_TIMESTAMP AND (lease_until IS NULL OR lease_until<CURRENT_TIMESTAMP)")
        .query(UUID::class.java).list().filterNotNull()
    fun claim(actor: UUID, automatic: Boolean): UUID? {
        jdbc.sql("INSERT INTO calendar_sync_schedule(actor_id) VALUES(:actor) ON CONFLICT DO NOTHING").param("actor",actor).update()
        val lease = UUID.randomUUID()
        val changed = jdbc.sql("""UPDATE calendar_sync_schedule SET lease_token=:lease,lease_until=:until,last_attempt_at=:now
            WHERE actor_id=:actor AND (lease_until IS NULL OR lease_until<:now)
            AND (:manual OR (enabled=TRUE AND next_attempt_at<=:now))
            AND (last_error IS DISTINCT FROM 'GOOGLE_RATE_LIMITED' OR next_attempt_at<=:now)""")
            .param("actor",actor).param("lease",lease).param("now",Timestamp.from(clock.instant()))
            .param("until",Timestamp.from(clock.instant().plusSeconds(1800))).param("manual",!automatic).update()
        return lease.takeIf { changed == 1 }
    }
    fun renew(actor: UUID, lease: UUID): Boolean = jdbc.sql("UPDATE calendar_sync_schedule SET lease_until=:until WHERE actor_id=:actor AND lease_token=:lease AND lease_until>:now")
        .param("actor",actor).param("lease",lease).param("now",Timestamp.from(clock.instant()))
        .param("until",Timestamp.from(clock.instant().plusSeconds(1800))).update() == 1
    fun finish(actor: UUID, lease: UUID, error: String?, retryAfter: Long? = null) {
        val previous = get(actor)
        val failed = error != null && error != "CALENDAR_SYNC_CONFLICT"
        val failures = if(failed) previous.failureCount + 1 else 0
        val delay = if(failed) calendarRetrySeconds(failures,retryAfter) else previous.intervalSeconds.toLong()
        jdbc.sql("""UPDATE calendar_sync_schedule SET lease_token=NULL,lease_until=NULL,last_error=:error,failure_count=:failures,
            last_success_at=CASE WHEN :success THEN :now ELSE last_success_at END,next_attempt_at=:next
            WHERE actor_id=:actor AND lease_token=:lease""")
            .param("actor",actor).param("lease",lease).param("error",error).param("failures",failures)
            .param("success",!failed && error == null).param("now",Timestamp.from(clock.instant()))
            .param("next",Timestamp.from(clock.instant().plusSeconds(delay))).update()
    }
}

@Service
class CalendarSyncRunner(private val repository: CalendarScheduleRepository, private val sync: CalendarSynchronization,
    private val rbac: RbacService, private val activity: ActivityService) {
    fun settings(actor: UUID): CalendarSchedule { rbac.require(actor,"calendar:read"); return repository.get(actor) }
    @org.springframework.transaction.annotation.Transactional
    fun configure(actor: UUID, body: CalendarScheduleRequest): CalendarSchedule {
        rbac.authorizeMutation(actor,"calendar:update")
        if(body.intervalSeconds !in 60..86400) throw InvalidCalendarEvent()
        if(body.enabled) permissions(actor)
        repository.configure(actor,body)
        activity.record(ActivityCategory.INTEGRATION,"calendar.schedule.configured",ActivityStatus.SUCCEEDED,
            ActivityActorType.USER,"kyrion-core","calendar.schedule.configured",actor.toString(),ownerId=rbac.workspace(actor))
        return repository.get(actor)
    }
    private fun permissions(actor: UUID) = listOf("calendar:read","calendar:create","calendar:update","calendar:delete").forEach { rbac.require(actor,it) }
    fun run(actor: UUID, automatic: Boolean = false): CalendarSyncResult {
        permissions(actor)
        val lease = repository.claim(actor,automatic) ?: throw CalendarSyncBusy()
        try {
            val result = sync.sync(actor, automatic) { if((automatic && !repository.get(actor).enabled) || !repository.renew(actor,lease)) throw CalendarSyncBusy() }
            repository.finish(actor,lease,result.errorCode ?: if(result.conflicts>0) "CALENDAR_SYNC_CONFLICT" else null,result.retryAfterSeconds)
            return result
        } catch(error: Exception) {
            val code = when(error) {
                is GoogleProviderException -> if(error.status==429) "GOOGLE_RATE_LIMITED" else "GOOGLE_UNAVAILABLE"
                is GoogleReauthorizationException -> "GOOGLE_REAUTHORIZATION_REQUIRED"
                is ForbiddenException -> "FORBIDDEN"
                else -> "GOOGLE_UNAVAILABLE"
            }
            repository.finish(actor,lease,code,(error as? GoogleProviderException)?.retryAfterSeconds)
            throw error
        }
    }
}

@Service
@ConditionalOnProperty(name=["kyrion.calendar.sync.scheduler-enabled"],havingValue="true",matchIfMissing=true)
class CalendarSyncScheduler(private val repository: CalendarScheduleRepository, private val runner: CalendarSyncRunner) {
    @Scheduled(fixedDelayString="\${kyrion.calendar.sync.scheduler-ms:15000}",initialDelay=15000)
    fun tick() { repository.due().forEach { actor -> try { runner.run(actor,true) } catch (_: ForbiddenException) { repository.suspend(actor) } catch (_: Exception) { /* bounded persisted status, no credentials logged */ } } }
}

@RestController
class CalendarScheduleController(private val runner: CalendarSyncRunner) {
    @GetMapping("/v1/calendar/sync/settings") fun get(request: HttpServletRequest)=runner.settings(request.authenticatedUserId())
    @PutMapping("/v1/calendar/sync/settings") fun put(@RequestBody body: CalendarScheduleRequest,request:HttpServletRequest)=runner.configure(request.authenticatedUserId(),body)
}
@ResponseStatus(HttpStatus.CONFLICT)
class CalendarSyncBusy: RuntimeException()
