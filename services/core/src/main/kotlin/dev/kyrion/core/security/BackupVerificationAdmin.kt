package dev.kyrion.core.security

import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.sql.DriverManager
import kotlin.system.exitProcess
import org.flywaydb.core.Flyway

/** Migration-only host operation. Never creates Spring beans or executes archived SQL. */
object BackupVerificationAdmin {
    private val target = Regex("jdbc:postgresql://127\\.0\\.0\\.1:([0-9]{4,5})/kyrion_verify_[0-9a-f]{32}")

    internal fun validateTarget(url: String) {
        val match = requireNotNull(target.matchEntire(url))
        require(match.groupValues[1].toInt() in 1024..65535)
    }

    @JvmStatic
    fun main(args: Array<String>) {
        if (args.contentEquals(arrayOf("--capability"))) {
            println("{\"formatVersion\":1,\"backupVerification\":1,\"coreSchema\":49,\"migrationOnly\":true}")
            return
        }
        try {
            require(args.contentEquals(arrayOf("--migrate-empty")))
            val url = requireNotNull(System.getenv("KYRION_BACKUP_VERIFICATION_DATABASE_URL"))
            validateTarget(url)
            val path = Path.of(requireNotNull(System.getenv("KYRION_DATABASE_PASSWORD_FILE")))
            require(Files.isRegularFile(path, NOFOLLOW_LINKS) && Files.size(path) in 16..256)
            val password = Files.readString(path).trimEnd('\r', '\n')
            require(password.length in 16..128 && password.none { it == '\n' || it == '\r' || it == '\u0000' })
            DriverManager.getConnection(url, "kyrion", password).use { connection ->
                connection.createStatement().use { statement ->
                    statement.executeQuery("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'").use {
                        require(it.next() && it.getLong(1) == 0L)
                    }
                }
            }
            Flyway.configure().dataSource(url, "kyrion", password)
                .locations("classpath:db/migration").cleanDisabled(true).load().migrate()
            println("{\"formatVersion\":1,\"backupVerification\":1,\"schemaPrepared\":true}")
        } catch (_: Exception) {
            System.err.println("E_BACKUP_VERIFICATION_SCHEMA")
            exitProcess(2)
        }
    }
}
