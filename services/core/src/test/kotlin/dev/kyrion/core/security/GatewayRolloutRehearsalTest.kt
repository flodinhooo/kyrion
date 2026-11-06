package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThat
import org.flywaydb.core.Flyway
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import org.springframework.core.io.support.PathMatchingResourcePatternResolver
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer
import java.nio.file.Files
import java.nio.file.Path
import java.sql.DriverManager
import java.util.UUID

/** Synthetic PostgreSQL only: no application configuration, provider or physical gateway. */
@Testcontainers
class GatewayRolloutRehearsalTest {
    @TempDir lateinit var directory: Path

    @Test fun `V41 backup restores through V42 V43 and old claim remains an unsafe rollback`() {
        val suffix = UUID.randomUUID().toString().replace("-", "")
        val source = "gateway_source_$suffix"
        val candidate = "gateway_candidate_$suffix"
        val rollback = "gateway_rollback_$suffix"
        val dump = "/tmp/gateway_$suffix.dump"
        fun command(vararg args: String) {
            val result = postgres.execInContainer(*args)
            assertThat(result.exitCode).withFailMessage("Synthetic container command failed: %s", result.stderr).isZero()
        }
        fun url(database: String) = "jdbc:postgresql://${postgres.host}:${postgres.getMappedPort(5432)}/$database"
        fun migration(database: String, version: String, location: String = "classpath:db/migration") = Flyway.configure()
            .dataSource(url(database), postgres.username, postgres.password).locations(location).target(version).load()
        fun connect(database: String) = DriverManager.getConnection(url(database), postgres.username, postgres.password)
        val owner = UUID.randomUUID()
        val node = UUID.randomUUID()
        val button = UUID.randomUUID()
        val target = UUID.randomUUID()
        val queued = UUID.randomUUID()
        for (database in listOf(source, candidate, rollback)) command("createdb", "-U", postgres.username, database)
        migration(source, "41").migrate()
        connect(source).use { connection -> connection.createStatement().use { sql ->
            sql.execute("INSERT INTO user_account(id,username,password_hash) VALUES('$owner','synthetic-gateway-owner','not-a-login-hash')")
            sql.execute("""INSERT INTO gateway_node(id,owner_id,display_name,hostname,credential_hash,agent_version,os_name,os_version,architecture,created_at,updated_at)
                VALUES('$node','$owner','Synthetic','synthetic',repeat('a',64),'test','test','test','test',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
            for ((id, address) in listOf(button to "0x0011223344556688", target to "0x0011223344556677")) {
                sql.execute("""INSERT INTO integration_connection(id,owner_id,provider,display_name,endpoint_host,credential_ciphertext,credential_nonce,created_at,updated_at)
                    VALUES('$id','$owner','zigbee','Synthetic','$address',decode('010203','hex'),decode('040506','hex'),CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""")
            }
            sql.execute("""INSERT INTO zigbee_button_binding(owner_id,button_connection_id,gesture,target_connection_id,action,updated_at)
                VALUES('$owner','$button','single','$target','turn_on',CURRENT_TIMESTAMP)""")
            sql.execute("""INSERT INTO gateway_command(id,node_id,owner_id,command_type,payload,status,created_at,correlation_id)
                VALUES('$queued','$node','$owner','zigbee.power','{"deviceId":"0x0011223344556677","on":true}','pending',CURRENT_TIMESTAMP,'$queued')""")
        } }
        command("pg_dump", "-U", postgres.username, "-Fc", "--no-owner", "--no-acl", "-f", dump, source)
        for (database in listOf(candidate, rollback)) command("pg_restore", "-U", postgres.username, "--exit-on-error", "--no-owner", "--no-acl", "-d", database, dump)
        migration(candidate, "43").migrate()
        migration(candidate, "43").validate()
        connect(candidate).use { connection -> connection.createStatement().use { sql ->
            sql.executeQuery("SELECT authority IS NULL AND status='pending' AND correlation_id=id AND payload->>'on'='true' FROM gateway_command WHERE id='$queued'").use {
                it.next(); assertThat(it.getBoolean(1)).isTrue()
            }
            sql.executeQuery("SELECT grant_id IS NULL AND granted_by IS NULL AND source_node_id IS NULL FROM zigbee_button_binding").use {
                it.next(); assertThat(it.getBoolean(1)).isTrue()
            }
            sql.executeQuery("SELECT count(*) FROM integration_connection WHERE encode(credential_ciphertext,'hex')='010203' AND encode(credential_nonce,'hex')='040506'").use {
                it.next(); assertThat(it.getInt(1)).isEqualTo(2)
            }
            // The exact pre-authority claim shape (fe5e65a): no actor/grant check.
            // Execute it only inside this disposable candidate to prove why old code is unsafe.
            sql.executeQuery("""UPDATE gateway_command SET status='running',claimed_at=CURRENT_TIMESTAMP
                WHERE id=(SELECT id FROM gateway_command WHERE node_id='$node' AND status='pending'
                ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING id""").use {
                assertThat(it.next()).isTrue(); assertThat(it.getObject(1, UUID::class.java)).isEqualTo(queued)
            }
            sql.execute("""INSERT INTO household_calendar_event(id,space_id,created_by,title,starts_at,ends_at,time_zone)
                VALUES('${UUID.randomUUID()}','$owner','$owner','Synthetic post-upgrade write',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP+INTERVAL '1 hour','UTC')""")
        } }
        // Model the migration resources present in the old artifact, without changing source/history.
        for (resource in PathMatchingResourcePatternResolver().getResources("classpath:db/migration/V*.sql")) {
            val name = requireNotNull(resource.filename)
            val version = Regex("V(\\d+)__.*").matchEntire(name)?.groupValues?.get(1)?.toInt() ?: continue
            if (version <= 41) resource.inputStream.use { Files.copy(it, directory.resolve(name)) }
        }
        val oldLocation = "filesystem:" + directory.toAbsolutePath().toString().replace('\\', '/')
        // Flyway's default future-migration tolerance is not an authority or rollback guarantee.
        migration(candidate, "41", oldLocation).validate()
        migration(rollback, "41", oldLocation).validate()
        for (database in listOf(source, rollback)) connect(database).use { connection -> connection.createStatement().use { sql ->
            sql.executeQuery("SELECT max(version::int) FROM flyway_schema_history WHERE success").use { it.next(); assertThat(it.getInt(1)).isEqualTo(41) }
            sql.executeQuery("SELECT status FROM gateway_command WHERE id='$queued'").use { it.next(); assertThat(it.getString(1)).isEqualTo("pending") }
            sql.executeQuery("SELECT to_regclass('public.household_calendar_event') IS NULL").use { it.next(); assertThat(it.getBoolean(1)).isTrue() }
        } }
        // All databases and dump die with this owned Testcontainer. No live database is a parameter.
    }

    companion object {
        @Container @JvmStatic val postgres = PostgreSQLContainer("postgres:17-alpine").withTmpFs(mapOf("/var/lib/postgresql/data" to "rw"))
    }
}
