package dev.kyrion.core.security

import org.springframework.stereotype.Component
import java.time.Instant

data class CentralDisplayProof(
    val issuer: String,
    val subject: String,
    val email: String?,
    val displayName: String?,
    val accessToken: String?,
    val expiresAt: Instant,
    val verifiedAt: Instant = Instant.now()
)

/** Short-lived verified proof only. No provider credential is persisted here. */
@Component
class CentralProofCache {
    private val proofs = LinkedHashMap<Pair<String, String>, CentralDisplayProof>()
    @Synchronized
    fun remember(proof: CentralDisplayProof) {
        proofs.entries.removeIf { !it.value.expiresAt.isAfter(Instant.now()) }
        if (proofs.size >= 256) proofs.remove(proofs.keys.first())
        proofs[proof.issuer to proof.subject] = proof
    }

    @Synchronized
    fun find(issuer: String, subject: String): CentralDisplayProof? =
        proofs[issuer to subject]?.takeIf { it.expiresAt.isAfter(Instant.now()) }
}
