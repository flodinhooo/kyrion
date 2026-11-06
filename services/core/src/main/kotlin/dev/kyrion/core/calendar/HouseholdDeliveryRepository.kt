package dev.kyrion.core.calendar

import org.springframework.http.HttpStatus
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.stereotype.Repository
import java.security.MessageDigest
import java.util.UUID

data class HouseholdDestinationSetting(val id: UUID?, val calendarId: String?, val enabled: Boolean, val revision: Long)
data class HouseholdDestinationChange(val calendarId: String?, val revision: Long)
data class HouseholdDeliveryTarget(val userId: UUID, val username: String, val targetId: UUID?)
data class HouseholdDeliveryView(val id: UUID, val userId: UUID, val username: String?, val state: String, val deliveredRevision: Long?, val errorCode: String?)
data class HouseholdDeliveries(val revision: Long, val targets: List<HouseholdDeliveryTarget>, val items: List<HouseholdDeliveryView>)
data class HouseholdDeliveryRequest(val targetId: UUID, val revision: Long)
internal data class DestinationGrant(val id: UUID, val space: UUID, val user: UUID, val connection: UUID?,
    val calendar: String?, val active: Boolean, val revision: Long, val username: String)
internal data class DeliveryRow(val id: UUID, val event: UUID, val user: UUID, val grant: UUID, val key: String,
    val remoteId: String, val etag: String?, val deliveredRevision: Long?, val writeStarted: Boolean,
    val state: String, val errorCode: String?, val attempt: UUID, val busy: Boolean)

@Repository
class HouseholdDeliveryRepository(private val jdbc: JdbcClient) {
    internal fun lock(space: UUID) {
        jdbc.sql("SELECT pg_advisory_xact_lock(hashtextextended(CAST(:space AS text),23))")
            .param("space", space).query { _, _ -> Unit }.single()
    }
    internal fun latest(space: UUID): List<DestinationGrant> = jdbc.sql("""SELECT DISTINCT ON(d.user_id) d.*,u.username
        FROM household_calendar_destination d JOIN user_account u ON u.id=d.user_id AND u.space_id=d.space_id
        WHERE d.space_id=:space ORDER BY d.user_id,d.revision DESC""").param("space", space).query { rs, _ -> grant(rs) }.list()
    internal fun grant(space: UUID, id: UUID): DestinationGrant? = jdbc.sql("""SELECT d.*,u.username FROM household_calendar_destination d
        JOIN user_account u ON u.id=d.user_id AND u.space_id=d.space_id WHERE d.space_id=:space AND d.id=:id""")
        .param("space", space).param("id", id).query { rs, _ -> grant(rs) }.optional().orElse(null)
    internal fun change(space: UUID, user: UUID, connection: UUID?, calendar: String?, revision: Long): UUID {
        jdbc.sql("UPDATE household_calendar_destination SET active=FALSE WHERE space_id=:space AND user_id=:user AND active")
            .param("space", space).param("user", user).update()
        val id = UUID.randomUUID()
        jdbc.sql("""INSERT INTO household_calendar_destination(id,space_id,user_id,connection_id,calendar_id,active,revision)
            VALUES(:id,:space,:user,:connection,:calendar,:active,:revision)""")
            .param("id", id).param("space", space).param("user", user).param("connection", connection)
            .param("calendar", calendar).param("active", calendar != null).param("revision", revision).update()
        return id
    }
    internal fun rows(space: UUID, event: UUID): List<DeliveryRow> = jdbc.sql("""SELECT *,
        (state='RUNNING' AND lease_until>CURRENT_TIMESTAMP) AS busy FROM household_calendar_delivery
        WHERE space_id=:space AND event_id=:event ORDER BY id""")
        .param("space", space).param("event", event).query { rs, _ -> delivery(rs) }.list()
    internal fun reserve(space: UUID, event: UUID, grant: DestinationGrant): DeliveryRow {
        val key = hash("${grant.connection}:${grant.calendar}")
        val previous = rows(space, event).find { it.user == grant.user && it.key == key }
        if (previous?.busy == true) throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_BUSY", HttpStatus.CONFLICT)
        val id = previous?.id ?: UUID.randomUUID()
        val remote = hash("$space:$event:${grant.user}:$key") // hexadecimal is valid Google base32hex.
        val attempt = UUID.randomUUID()
        jdbc.sql("""INSERT INTO household_calendar_delivery(id,space_id,event_id,target_user_id,grant_id,destination_key,remote_id,state,attempt_id,lease_until)
            VALUES(:id,:space,:event,:user,:grant,:key,:remote,'RUNNING',:attempt,CURRENT_TIMESTAMP+INTERVAL '5 minutes')
            ON CONFLICT(event_id,target_user_id,destination_key) DO UPDATE SET grant_id=EXCLUDED.grant_id,
            state='RUNNING',error_code=NULL,attempt_id=EXCLUDED.attempt_id,lease_until=EXCLUDED.lease_until,updated_at=CURRENT_TIMESTAMP""")
            .param("id", id).param("space", space).param("event", event).param("user", grant.user)
            .param("grant", grant.id).param("key", key).param("remote", remote).param("attempt", attempt).update()
        return rows(space, event).first { it.id == id }
    }
    internal fun current(space: UUID, row: DeliveryRow): Boolean = rows(space, row.event).any { it.id == row.id && it.attempt == row.attempt && it.busy }
    internal fun writeStarted(space: UUID, row: DeliveryRow) {
        if (jdbc.sql("""UPDATE household_calendar_delivery SET write_started=TRUE,updated_at=CURRENT_TIMESTAMP
            WHERE space_id=:space AND id=:id AND attempt_id=:attempt AND state='RUNNING' AND lease_until>CURRENT_TIMESTAMP""")
                .param("space", space).param("id", row.id).param("attempt", row.attempt).update() != 1)
            throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_BUSY", HttpStatus.CONFLICT)
    }
    internal fun finish(space: UUID, row: DeliveryRow, state: String, error: String?, revision: Long?, etag: String?): Boolean =
        jdbc.sql("""UPDATE household_calendar_delivery SET state=:state,error_code=:error,
            delivered_revision=COALESCE(:revision,delivered_revision),etag=COALESCE(:etag,etag),updated_at=CURRENT_TIMESTAMP
            WHERE space_id=:space AND id=:id AND attempt_id=:attempt AND state='RUNNING'""")
            .param("space", space).param("id", row.id).param("attempt", row.attempt).param("state", state)
            .param("error", error).param("revision", revision).param("etag", etag).update() == 1
    internal fun clearDefinitivelyDeniedInsert(space: UUID, row: DeliveryRow) {
        jdbc.sql("UPDATE household_calendar_delivery SET write_started=FALSE WHERE space_id=:space AND id=:id AND attempt_id=:attempt AND delivered_revision IS NULL AND etag IS NULL")
            .param("space", space).param("id", row.id).param("attempt", row.attempt).update()
    }
    fun retainedCopies(space: UUID, event: UUID, acknowledged: Boolean): List<UUID> {
        val rows = rows(space, event)
        if (rows.any { it.busy }) throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_BUSY", HttpStatus.CONFLICT)
        if (rows.isNotEmpty() && !acknowledged) throw HouseholdDeliveryFailure("CALENDAR_DELIVERY_RETENTION_REQUIRED", HttpStatus.CONFLICT)
        return rows.map { it.id }
    }
    private fun grant(rs: java.sql.ResultSet) = DestinationGrant(rs.getObject("id", UUID::class.java), rs.getObject("space_id", UUID::class.java),
        rs.getObject("user_id", UUID::class.java), rs.getObject("connection_id", UUID::class.java), rs.getString("calendar_id"),
        rs.getBoolean("active"), rs.getLong("revision"), rs.getString("username"))
    private fun delivery(rs: java.sql.ResultSet) = DeliveryRow(rs.getObject("id", UUID::class.java), rs.getObject("event_id", UUID::class.java),
        rs.getObject("target_user_id", UUID::class.java), rs.getObject("grant_id", UUID::class.java), rs.getString("destination_key"),
        rs.getString("remote_id"), rs.getString("etag"), (rs.getObject("delivered_revision") as? Number)?.toLong(),
        rs.getBoolean("write_started"), rs.getString("state"), rs.getString("error_code"), rs.getObject("attempt_id", UUID::class.java), rs.getBoolean("busy"))
    private fun hash(value: String) = MessageDigest.getInstance("SHA-256").digest(value.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
}
