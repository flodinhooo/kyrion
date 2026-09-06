package dev.kyrion.core.security

interface UserAccountRepository {
    fun exists(): Boolean
    fun createOwner(account: UserAccount): UserAccount?
    fun createInvitation(invitation: RegistrationInvitation)
    fun register(account: UserAccount, invitationHash: String, now: java.time.Instant): UserAccount?
    fun findByUsername(username: String): UserAccount?
    fun findById(id: java.util.UUID): UserAccount?
    fun updatePassword(id: java.util.UUID, passwordHash: String, updatedAt: java.time.Instant): Boolean
}
