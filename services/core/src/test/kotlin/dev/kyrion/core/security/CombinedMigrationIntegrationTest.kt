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
