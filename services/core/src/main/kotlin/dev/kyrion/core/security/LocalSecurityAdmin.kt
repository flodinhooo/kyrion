package dev.kyrion.core.security

import dev.kyrion.core.activity.*
import java.nio.file.Files
import java.nio.file.LinkOption.NOFOLLOW_LINKS
import java.nio.file.Path
import java.nio.file.StandardOpenOption
import java.nio.file.attribute.AclEntryPermission
import java.nio.file.attribute.AclEntryType
import java.nio.file.attribute.AclFileAttributeView
import java.nio.file.attribute.PosixFilePermissions
import java.util.UUID
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.jdbc.datasource.DataSourceTransactionManager
import org.springframework.jdbc.datasource.DriverManagerDataSource
import org.springframework.transaction.support.TransactionTemplate

/** Host-only entry point via Boot PropertiesLauncher; never starts the HTTP application. */
object LocalSecurityAdmin {
    @JvmStatic
    fun main(args: Array<String>) {
        val console =
            System.console()
                ?: error("Interactive host console required; redirected input/output is prohibited")
        require(args.size in 3..5) {
            "Usage: provision|open|complete|rotate|attest SPACE_UUID HOST_KEY_FILE [USER_UUID EMAIL]"
        }
        val command = args[0]
        require(command in setOf("provision", "open", "complete", "rotate", "attest"))
        val space = UUID.fromString(args[1])
        val path = Path.of(args[2]).toAbsolutePath().normalize()
        val url = required("KYRION_DATABASE_URL")
        val dbPassword =
            System.getenv("KYRION_DATABASE_PASSWORD_FILE")?.let {
                Files.readString(Path.of(it)).trimEnd('\r', '\n')
            } ?: required("KYRION_DATABASE_PASSWORD")
        val dataSource = DriverManagerDataSource(url, required("KYRION_DATABASE_USER"), dbPassword)
        val jdbc = JdbcClient.create(dataSource)
        val transactions = TransactionTemplate(DataSourceTransactionManager(dataSource))
        val integrity = ActivityIntegrity(required("KYRION_AUDIT_INTEGRITY_KEY_FILE"), false)
        require(ActivityIntegrityVerifier(jdbc, integrity).verify(space.toString()).valid) {
            "Existing audit chain does not validate with this installation key; recovery is blocked"
        }
        val activity = ActivityService(JdbcActivityEventRepository(jdbc, transactions, integrity))
        val recovery =
            LocalOwnerRecovery(
                jdbc,
                transactions,
                PasswordHashingService(),
                activity,
                operator = System.getProperty("user.name", "host-administrator"),
            )
        fun secret(prompt: String): String {
            val chars = console.readPassword("%s: ", prompt) ?: error("Input required")
            return try {
                String(chars)
            } finally {
                chars.fill('\u0000')
            }
        }
        try {
            if (command == "provision") {
                require(!Files.exists(path, NOFOLLOW_LINKS)) {
                    "Host key already exists; never overwrite recovery material"
                }
                require(Files.isDirectory(path.parent, NOFOLLOW_LINKS)) {
                    "Provision a protected parent directory first"
                }
                val host = SessionTokenService().create().rawToken
                if (Files.getFileStore(path.parent).supportsFileAttributeView("posix")) {
                    Files.newByteChannel(
                            path,
                            setOf(StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE),
                            PosixFilePermissions.asFileAttribute(
                                PosixFilePermissions.fromString("rw-------")
                            ),
                        )
                        .use { it.write(java.nio.ByteBuffer.wrap(host.toByteArray())) }
                } else
                    Files.writeString(
                        path,
                        host,
                        StandardOpenOption.CREATE_NEW,
                        StandardOpenOption.WRITE,
                    )
                try {
                    ProtectedSecurityFile.read(path)
                    val code = recovery.provision(space, secret("Current OWNER password"), host)
                    console.printf(
                        "Store this offline recovery code privately. It is shown once:%n%s%n",
                        code,
                    )
                } catch (failure: Exception) {
                    Files.deleteIfExists(path)
                    throw failure
                }
            } else {
                val host = ProtectedSecurityFile.read(path)
                when (command) {
                    "rotate" ->
                        console.printf(
                            "New offline code (previous codes and recovery sessions invalidated):%n%s%n",
                            recovery.rotate(space, host, secret("Current OWNER password")),
                        )
                    "open" -> {
                        val opened = recovery.open(space, host, secret("Offline recovery code"))
                        console.printf(
                            "One-use recovery session (5 minutes):%n%s%nNew offline code (store now; previous code consumed):%n%s%n",
                            opened.session,
                            opened.nextCode,
                        )
                    }
                    "complete" -> {
                        val session = secret("Recovery session")
                        val password = secret("New OWNER password")
                        require(password == secret("Repeat new password")) { "Password mismatch" }
                        console.printf(
                            "Recovery completed. Store the new offline recovery code; the old code is invalid:%n%s%n",
                            recovery.complete(space, host, session, password),
                        )
                    }
                    "attest" -> {
                        require(args.size == 5)
                        console.printf(
                            "Local attestation is NOT mailbox or DNS verification. Continue only after independently checking identity.%n"
                        )
                        require(console.readLine("Type ATTEST to confirm: ") == "ATTEST")
                        recovery.attestEmail(
                            space,
                            host,
                            secret("Current OWNER password"),
                            UUID.fromString(args[3]),
                            args[4],
                        )
                        console.printf(
                            "Local attestation recorded; strict SMTP proof is not satisfied.%n"
                        )
                    }
                }
            }
        } catch (_: Exception) {
            error(
                "Local security operation failed; no remote recovery or bypass is available. Check the local audit log and configuration."
            )
        }
    }

    private fun required(name: String) =
        System.getenv(name)?.takeIf { it.isNotBlank() } ?: error("Missing $name")
}

object ProtectedSecurityFile {
    fun read(path: Path): String {
        require(Files.isRegularFile(path, NOFOLLOW_LINKS) && Files.size(path) in 43..128) {
            "Protected regular file required"
        }
        if (Files.getFileStore(path).supportsFileAttributeView("posix")) {
            val mode = Files.getPosixFilePermissions(path, NOFOLLOW_LINKS)
            require(mode.none { it.name.startsWith("GROUP_") || it.name.startsWith("OTHERS_") }) {
                "Owner-only file required"
            }
        } else {
            val view =
                Files.getFileAttributeView(path, AclFileAttributeView::class.java, NOFOLLOW_LINKS)
                    ?: error("ACL checks unavailable")
            val owner = view.owner
            val sensitive =
                setOf(
                    AclEntryPermission.READ_DATA,
                    AclEntryPermission.WRITE_DATA,
                    AclEntryPermission.APPEND_DATA,
                    AclEntryPermission.WRITE_ACL,
                    AclEntryPermission.WRITE_OWNER,
                )
            require(
                view.acl.none { entry ->
                    val principal = entry.principal().name.uppercase()
                    entry.type() == AclEntryType.ALLOW &&
                        entry.principal() != owner &&
                        !principal.endsWith("\\SYSTEM") &&
                        !principal.endsWith("\\ADMINISTRATORS") &&
                        entry.permissions().any { it in sensitive }
                }
            ) {
                "Owner, SYSTEM and Administrators only ACL required"
            }
        }
        return Files.readString(path).trim().also {
            require(it.matches(Regex("[A-Za-z0-9_-]{43}")))
        }
    }
}
