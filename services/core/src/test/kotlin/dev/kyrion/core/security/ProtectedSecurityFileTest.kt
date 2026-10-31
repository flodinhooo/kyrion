package dev.kyrion.core.security

import java.nio.file.Files
import java.nio.file.attribute.AclEntry
import java.nio.file.attribute.AclEntryPermission
import java.nio.file.attribute.AclEntryType
import java.nio.file.attribute.AclFileAttributeView
import java.nio.file.attribute.PosixFilePermissions
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test

class ProtectedSecurityFileTest {
    @Test
    fun `host material requires a protected regular file and a valid random token format`() {
        val path = Files.createTempFile("kyrion-host-material-test", ".key")
        try {
            if (Files.getFileStore(path).supportsFileAttributeView("posix")) {
                Files.setPosixFilePermissions(path, PosixFilePermissions.fromString("rw-------"))
            } else {
                val acl = Files.getFileAttributeView(path, AclFileAttributeView::class.java)
                acl.acl =
                    listOf(
                        AclEntry.newBuilder()
                            .setType(AclEntryType.ALLOW)
                            .setPrincipal(acl.owner)
                            .setPermissions(*AclEntryPermission.entries.toTypedArray())
                            .build()
                    )
            }
            val code = SessionTokenService().create().rawToken
            Files.writeString(path, code)
            assertThat(ProtectedSecurityFile.read(path)).isEqualTo(code)
            Files.writeString(path, "invalid")
            assertThatThrownBy { ProtectedSecurityFile.read(path) }
                .isInstanceOf(IllegalArgumentException::class.java)
        } finally {
            Files.deleteIfExists(path)
        }
    }
}
