package dev.kyrion.core.security

interface UserAccountRepository {
    fun exists(): Boolean
    fun createOwner(account: UserAccount): UserAccount?
    fun findByUsername(username: String): UserAccount?
    fun findById(id: java.util.UUID): UserAccount?
    fun updatePassword(id: java.util.UUID, passwordHash: String, updatedAt: java.time.Instant): Boolean
}
