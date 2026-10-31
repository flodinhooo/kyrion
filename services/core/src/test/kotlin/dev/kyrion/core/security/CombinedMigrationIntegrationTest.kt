package dev.kyrion.core.security

import java.nio.file.Files
import java.nio.file.Path
import java.sql.DriverManager
import java.util.UUID
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.flywaydb.core.Flyway
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import org.testcontainers.junit.jupiter.Container
import org.testcontainers.junit.jupiter.Testcontainers
import org.testcontainers.postgresql.PostgreSQLContainer

@Testcontainers
class CombinedMigrationIntegrationTest {
    @TempDir lateinit var temp: Path

    private fun flyway(location: String = "classpath:db/migration", target: String? = null) =
        Flyway.configure()
            .dataSource(postgres.jdbcUrl, postgres.username, postgres.password)
            .locations(location)
            .apply { if (target != null) target(target) }
            .load()

    @Test
    fun `V33 upgrade preserves real installation shaped records and restricts grants`() {
        // Each test gets a private schema in the disposable database, never the live DB.
        val schema = "upgrade_" + UUID.randomUUID().toString().replace("-", "")
        val config = { target: String? ->
            Flyway.configure()
                .dataSource(postgres.jdbcUrl, postgres.username, postgres.password)
                .schemas(schema)
                .defaultSchema(schema)
                .locations("classpath:db/migration")
                .apply { if (target != null) target(target) }
                .load()
        }
        config("33").migrate()
        DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password).use {
            connection ->
            connection.schema = schema
            val owner = UUID.randomUUID()
            val audit = UUID.randomUUID()
            connection.createStatement().use { statement ->
                statement.execute(
                    "INSERT INTO user_account(id,username,password_hash) VALUES('$owner','upgrade-fixture','fixture-hash')"
                )
                statement.execute("UPDATE installation_bootstrap_state SET initialized=TRUE")
                statement.execute(
                    "INSERT INTO auth_session(id,user_id,token_hash,expires_at) VALUES(gen_random_uuid(),'$owner',repeat('a',64),CURRENT_TIMESTAMP+INTERVAL '1 day')"
                )
                statement.execute(
                    "INSERT INTO rbac_role(id,installation_owner_id,role_key,display_name,system_role) VALUES(gen_random_uuid(),'$owner','USER','Restricted',TRUE)"
                )
                statement.execute(
                    "INSERT INTO rbac_role_permission SELECT id,'devices:read' FROM rbac_role"
                )
                statement.execute(
                    "INSERT INTO personal_memory(id,owner_id,category,content,sensitivity,origin,status,created_at,updated_at,confirmed_at) VALUES(gen_random_uuid(),'$owner','other','synthetic remembered value','standard','explicit','confirmed',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                )
                statement.execute(
                    "INSERT INTO owner_memory_settings(owner_id,enabled,updated_at) VALUES('$owner',TRUE,CURRENT_TIMESTAMP)"
                )
                statement.execute(
                    "INSERT INTO local_calendar_event(id,owner_id,title,starts_at,ends_at,time_zone,content_fingerprint,created_at,updated_at) VALUES(gen_random_uuid(),'$owner','synthetic event',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP+INTERVAL '1 hour','Europe/Zurich','test',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                )
                statement.execute(
                    "INSERT INTO integration_connection(id,owner_id,provider,display_name,endpoint_host,credential_ciphertext,credential_nonce,created_at,updated_at) VALUES(gen_random_uuid(),'$owner','home_assistant','fixture','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',decode('0102','hex'),decode('0304','hex'),CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                )
                statement.execute(
                    "INSERT INTO activity_event(id,occurred_at,category,event_type,status,actor_type,source,correlation_id,summary_code,owner_id,integrity_version,chain_scope,event_hash) VALUES('$audit',CURRENT_TIMESTAMP,'SECURITY','synthetic.upgrade','SUCCEEDED','SYSTEM','test','$audit','synthetic.audit.marker','$owner',1,'owner:$owner',decode(repeat('11',32),'hex'))"
                )
                statement.execute(
                    "INSERT INTO activity_integrity_chain(chain_scope,last_event_id,last_hash,updated_at) VALUES('owner:$owner','$audit',decode(repeat('11',32),'hex'),CURRENT_TIMESTAMP)"
                )
            }
            config(null).migrate()
            config(null).validate()
            connection.createStatement().use { statement ->
                statement.executeQuery("SELECT space_id=id FROM user_account").use {
                    it.next()
                    assertThat(it.getBoolean(1)).isTrue()
                }
                statement.executeQuery("SELECT permission_key FROM rbac_role_permission").use {
                    it.next()
                    assertThat(it.getString(1)).isEqualTo("devices:read")
                    assertThat(it.next()).isFalse()
                }
                statement
                    .executeQuery("SELECT content,active,expires_at FROM personal_memory")
                    .use {
                        it.next()
                        assertThat(it.getString(1)).isEqualTo("synthetic remembered value")
                        assertThat(it.getBoolean(2)).isTrue()
                        assertThat(it.getObject(3)).isNull()
                    }
                statement
                    .executeQuery("SELECT enabled,kyrion_data_enabled FROM owner_memory_settings")
                    .use {
                        it.next()
                        assertThat(it.getBoolean(1)).isTrue()
                        assertThat(it.getBoolean(2)).isFalse()
                    }
                statement
                    .executeQuery("SELECT count(*) FROM auth_session WHERE revoked_at IS NULL")
                    .use {
                        it.next()
                        assertThat(it.getInt(1)).isEqualTo(1)
                    }
                statement.executeQuery("SELECT title,time_zone FROM local_calendar_event").use {
                    it.next()
                    assertThat(it.getString(1)).isEqualTo("synthetic event")
                    assertThat(it.getString(2)).isEqualTo("Europe/Zurich")
                }
                statement
                    .executeQuery(
                        "SELECT encode(credential_ciphertext,'hex'),encode(credential_nonce,'hex') FROM integration_connection"
                    )
                    .use {
                        it.next()
                        assertThat(it.getString(1)).isEqualTo("0102")
                        assertThat(it.getString(2)).isEqualTo("0304")
                    }
                statement
                    .executeQuery(
                        "SELECT summary_code,encode(event_hash,'hex') FROM activity_event WHERE id='$audit'"
                    )
                    .use {
                        it.next()
                        assertThat(it.getString(1)).isEqualTo("synthetic.audit.marker")
                        assertThat(it.getString(2)).isEqualTo("11".repeat(32))
                    }
                statement
                    .executeQuery(
                        "SELECT last_event_id FROM activity_integrity_chain WHERE chain_scope='owner:$owner'"
                    )
                    .use {
                        it.next()
                        assertThat(it.getObject(1, UUID::class.java)).isEqualTo(audit)
                    }
            }
        }
    }

    @Test
    fun `V40 preserves legacy charges and closes unknown invocation history without guessing prices`() {
        val schema = "usage_" + UUID.randomUUID().toString().replace("-", "")
        fun config(target: String? = null) = Flyway.configure()
            .dataSource(postgres.jdbcUrl, postgres.username, postgres.password)
            .schemas(schema).defaultSchema(schema).locations("classpath:db/migration")
            .apply { if (target != null) target(target) }.load()
        config("39").migrate()
        DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password).use { connection ->
            connection.schema = schema
            val owner = UUID.randomUUID()
            connection.createStatement().use { statement ->
                statement.execute("INSERT INTO user_account(id,username,password_hash) VALUES('$owner','usage-upgrade','fixture')")
                for (state in listOf("pending", "uncertain", "estimated", "reported", "rejected")) {
                    statement.execute("""INSERT INTO ai_usage_attempt(id,actor_id,request_id,attempt,provider,profile_id,model_id,
                        period,charged_tokens,estimated_cost,currency,state) VALUES(gen_random_uuid(),'$owner',gen_random_uuid(),0,
                        'ollama','fixture','fixture','2026-09',116,NULL,NULL,'$state')""")
                }
            }
            config().migrate()
            config().validate()
            connection.createStatement().use { statement ->
                statement.executeQuery("SELECT COUNT(*) FROM ai_usage_attempt WHERE reserved_tokens=116 AND charged_tokens=116 AND reserved_cost IS NULL AND input_price IS NULL AND invoked_at IS NULL").use {
                    it.next(); assertThat(it.getInt(1)).isEqualTo(5)
                }
                statement.executeQuery("SELECT COUNT(*) FROM ai_usage_attempt WHERE state='pending'").use {
                    it.next(); assertThat(it.getInt(1)).isZero()
                }
                statement.executeQuery("SELECT COUNT(*) FROM ai_usage_attempt WHERE state='uncertain' AND error_code='LEGACY_REVIEW_REQUIRED'").use {
                    it.next(); assertThat(it.getInt(1)).isEqualTo(1)
                }
            }
        }
    }

    @Test
    fun `V40 rollout rehearses real dump restore and retains an unmodified V39 rollback database`() {
        val suffix = UUID.randomUUID().toString().replace("-", "")
        val original = "rollout_original_$suffix"
        val restored = "rollout_restored_$suffix"
        val dump = "/tmp/rollout_$suffix.dump"
        val actor = UUID.randomUUID()
        fun url(database: String) = "jdbc:postgresql://${postgres.host}:${postgres.getMappedPort(5432)}/$database"
        fun config(database: String, version: String? = null) = Flyway.configure()
            .dataSource(url(database), postgres.username, postgres.password)
            .locations("classpath:db/migration").apply { if (version != null) target(version) }.load()
        fun command(vararg args: String) {
            val result = postgres.execInContainer(*args)
            assertThat(result.exitCode).withFailMessage("Isolated rollout command failed: ${args.first()}").isZero()
        }
        command("createdb", "-U", postgres.username, original)
        command("createdb", "-U", postgres.username, restored)
        try {
            config(original, "39").migrate()
            DriverManager.getConnection(url(original), postgres.username, postgres.password).use { connection ->
                connection.createStatement().use { sql ->
                    sql.execute("INSERT INTO user_account(id,username,password_hash) VALUES('$actor','synthetic-rollout','fixture-hash')")
                    sql.execute("""INSERT INTO ai_usage_attempt(id,actor_id,request_id,attempt,provider,profile_id,model_id,period,charged_tokens,estimated_cost,currency,state)
                        VALUES(gen_random_uuid(),'$actor',gen_random_uuid(),0,'ollama','fixture','fixture','2026-09',116,0.000264,'USD','pending')""")
                }
            }
            command("pg_dump", "-U", postgres.username, "-d", original, "--format=custom", "--file=$dump")
            command("pg_restore", "-U", postgres.username, "-d", restored, "--exit-on-error", dump)
            config(restored).migrate()
            config(restored).validate()
            for ((database, version) in listOf(original to "39", restored to "40")) {
                DriverManager.getConnection(url(database), postgres.username, postgres.password).use { connection ->
                    connection.createStatement().use { sql ->
                        sql.executeQuery("SELECT MAX(version::int) FROM flyway_schema_history WHERE success").use {
                            it.next(); assertThat(it.getString(1)).isEqualTo(version)
                        }
                        sql.executeQuery("SELECT id,username,password_hash FROM user_account").use {
                            it.next(); assertThat(it.getObject(1, UUID::class.java)).isEqualTo(actor)
                            assertThat(it.getString(2)).isEqualTo("synthetic-rollout")
                            assertThat(it.getString(3)).isEqualTo("fixture-hash")
                        }
                        val projection = if (version == "40") "state,charged_tokens,reserved_tokens,estimated_cost,reserved_cost" else "state,charged_tokens,charged_tokens,estimated_cost,estimated_cost"
                        sql.executeQuery("SELECT $projection FROM ai_usage_attempt").use {
                            it.next(); assertThat(it.getString(1)).isEqualTo(if (version == "40") "uncertain" else "pending")
                            assertThat(it.getLong(2)).isEqualTo(116); assertThat(it.getLong(3)).isEqualTo(116)
                            assertThat(it.getBigDecimal(4)).isEqualByComparingTo("0.000264")
                            assertThat(it.getBigDecimal(5)).isEqualByComparingTo("0.000264")
                        }
                    }
                }
            }
            config(original, "39").validate() // Rollback means returning to preserved V39, never downgrading V40.
        } finally {
            command("dropdb", "-U", postgres.username, "--if-exists", restored)
            command("dropdb", "-U", postgres.username, "--if-exists", original)
            command("rm", "-f", dump)
        }
    }

    @Test
    fun `incompatible already applied feature history fails validation without repair`() {
        val resources = Path.of(javaClass.getResource("/db/migration")!!.toURI())
        Files.list(resources).use { files ->
            files.forEach { source ->
                val version =
                    source.fileName.toString().substringBefore("__").removePrefix("V").toIntOrNull()
                if (version != null && version <= 34)
                    Files.copy(source, temp.resolve(source.fileName))
            }
        }
        Files.copy(
            resources.resolve("V38__kyrion_spaces.sql"),
            temp.resolve("V37__kyrion_spaces.sql"),
        )
        Files.copy(
            resources.resolve("V39__business_identity_and_local_recovery.sql"),
            temp.resolve("V38__business_identity_and_local_recovery.sql"),
        )
        val schema = "legacy_" + UUID.randomUUID().toString().replace("-", "")
        val config = { location: String ->
            Flyway.configure()
                .dataSource(postgres.jdbcUrl, postgres.username, postgres.password)
                .schemas(schema)
                .defaultSchema(schema)
                .locations(location)
                .load()
        }
        config("filesystem:$temp").migrate()
        assertThatThrownBy { config("classpath:db/migration").migrate() }
            .isInstanceOf(org.flywaydb.core.api.exception.FlywayValidateException::class.java)
        DriverManager.getConnection(postgres.jdbcUrl, postgres.username, postgres.password).use {
            connection ->
            connection.schema = schema
            connection.createStatement().use { statement ->
                statement
                    .executeQuery("SELECT script FROM flyway_schema_history WHERE version='37'")
                    .use {
                        it.next()
                        assertThat(it.getString(1)).isEqualTo("V37__kyrion_spaces.sql")
                    }
            }
        }
    }

    companion object {
        @Container
        @JvmStatic
        val postgres =
            PostgreSQLContainer("postgres:17-alpine")
                .withStartupTimeout(java.time.Duration.ofMinutes(3))
    }
}
