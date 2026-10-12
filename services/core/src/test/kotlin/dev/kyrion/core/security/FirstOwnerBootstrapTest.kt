package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.io.TempDir
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.FileTime
import java.time.Clock
import java.time.Instant
import java.time.ZoneOffset

class FirstOwnerBootstrapTest {
    @TempDir
    lateinit var directory: Path
    private val now = Instant.parse("2026-10-11T12:00:00Z")
    private val clock = Clock.fixed(now, ZoneOffset.UTC)

    @Test
    fun `missing malformed expired and future files fail closed`() {
        val secret = SessionTokenService().create().rawToken
        val path = directory.resolve("bootstrap.secret")
        val guard = FirstOwnerBootstrap(path.toString(), clock)
        assertThatThrownBy { guard.verify(secret) }.isInstanceOf(BootstrapForbiddenException::class.java)
        Files.writeString(path, "not-a-secret")
        Files.setLastModifiedTime(path, FileTime.from(now))
        assertThatThrownBy { guard.verify(secret) }.isInstanceOf(BootstrapForbiddenException::class.java)
        Files.writeString(path, secret)
        if (Files.getFileStore(path).supportsFileAttributeView("posix")) Files.setPosixFilePermissions(
            path,
            setOf(
                java.nio.file.attribute.PosixFilePermission.OWNER_READ,
                java.nio.file.attribute.PosixFilePermission.OWNER_WRITE
            )
        )
        Files.setLastModifiedTime(path, FileTime.from(now))
        guard.verify(secret)
        Files.setLastModifiedTime(path, FileTime.from(now.minusSeconds(1801)))
        assertThatThrownBy { guard.verify(secret) }.isInstanceOf(BootstrapForbiddenException::class.java)
        Files.setLastModifiedTime(path, FileTime.from(now.plusSeconds(60)))
        assertThatThrownBy { guard.verify(secret) }.isInstanceOf(BootstrapForbiddenException::class.java)
    }

    @Test
    fun `bounded failed attempts throttle bootstrap verification`() {
        val guard = FirstOwnerBootstrap("", clock)
        repeat(5) { assertThatThrownBy { guard.verify(null) }.isInstanceOf(BootstrapForbiddenException::class.java) }
        assertThatThrownBy { guard.verify(null) }.isInstanceOf(LoginRateLimitedException::class.java)
    }
}
