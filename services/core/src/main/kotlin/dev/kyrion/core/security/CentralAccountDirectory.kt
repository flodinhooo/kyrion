package dev.kyrion.core.security

import com.fasterxml.jackson.databind.JsonNode
import com.fasterxml.jackson.module.kotlin.jacksonObjectMapper
import dev.kyrion.core.integration.CredentialCipher
import dev.kyrion.core.integration.ProtectedCredential
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.springframework.beans.factory.annotation.Value
import org.springframework.jdbc.core.simple.JdbcClient
import org.springframework.scheduling.annotation.Scheduled
import org.springframework.stereotype.Service
import org.slf4j.LoggerFactory
import org.springframework.web.bind.annotation.GetMapping
import org.springframework.web.bind.annotation.RestController
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.sql.Timestamp
import java.time.Duration
import java.time.Instant
import java.util.UUID
import java.util.concurrent.TimeUnit

data class ConnectedCentralAccount(val displayName: String?, val email: String?)
data class CentralAccountView(
    val linked: Boolean,
    val issuer: String? = null,
    val linkedAt: Instant? = null,
    val account: ConnectedCentralAccount? = null,
    val directoryState: String? = null
)

@Service
class CentralAccountDirectory(
    private val jdbc: JdbcClient,
    private val authentication: LocalAuthenticationService,
    private val proofs: CentralProofCache,
    private val cipher: CredentialCipher,
    @Value("\${KYRION_CENTRAL_ISSUER:}") issuer: String = "",
    @Value("\${KYRION_ACCOUNT_DIRECTORY_ORIGIN:}") configuredOrigin: String = "",
    @Value("\${KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP:false}") allowLoopback: Boolean = false,
) {
    private val log = LoggerFactory.getLogger(CentralAccountDirectory::class.java)
    private val mapper = jacksonObjectMapper()
    private val http =
        HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).followRedirects(HttpClient.Redirect.NEVER).build()
    private val origin =
        (configuredOrigin.ifBlank { if (issuer == "https://auth.kyrion.ch/realms/kyrion") "https://www.kyrion.ch" else "" }).takeIf(
            String::isNotBlank
        )?.let {
            URI(it).also { uri ->
                require(
                    uri.host != null && uri.userInfo == null && uri.query == null && uri.fragment == null && uri.path in listOf(
                        "",
                        "/"
                    )
                )
                require(
                    uri.scheme == "https" || (allowLoopback && uri.scheme == "http" && uri.host in setOf(
                        "localhost",
                        "127.0.0.1"
                    ))
                )
            }
        }

    fun account(rawSession: String): CentralAccountView {
        val user = authentication.authenticate(rawSession) ?: throw UnauthenticatedException()
        return jdbc.sql(
            """SELECT l.issuer,l.subject,l.linked_at,p.email,p.display_name,p.synchronized_at
            FROM central_identity_link l LEFT JOIN central_account_profile p
            ON p.user_id=l.user_id AND p.issuer=l.issuer AND p.subject=l.subject WHERE l.user_id=:user"""
        )
            .param("user", user.id).query { rs, _ ->
                val proof = proofs.find(rs.getString("issuer"), rs.getString("subject"))
                val email = proof?.email ?: rs.getString("email")
                val name = proof?.displayName ?: rs.getString("display_name")
                CentralAccountView(
                    true, rs.getString("issuer"), rs.getTimestamp("linked_at").toInstant(),
                    if (email != null || name != null) ConnectedCentralAccount(name, email) else null,
                    if (origin == null) "not_available" else if (rs.getTimestamp("synchronized_at") != null) "confirmed" else "pending"
                )
            }.optional().orElse(CentralAccountView(false))
    }

    /** Directory availability never decides local authorization or linking success. */
    @Scheduled(fixedDelay = 5000, initialDelay = 5000)
    @Synchronized
    fun synchronize() {
        val links = jdbc.sql(
            """SELECT l.user_id,l.issuer,l.subject,l.linked_at,u.username,s.id AS installation_id,s.name,s.type
            FROM central_identity_link l JOIN user_account u ON u.id=l.user_id JOIN kyrion_space s ON s.id=u.space_id
            ORDER BY l.linked_at LIMIT 100"""
        ).query { rs, _ ->
            Link(
                rs.getObject("user_id", UUID::class.java),
                rs.getString("issuer"),
                rs.getString("subject"),
                rs.getTimestamp("linked_at").toInstant(),
                rs.getString("username"),
                rs.getObject("installation_id", UUID::class.java),
                rs.getString("name"),
                rs.getString("type")
            )
        }.list()
        for (link in links) {
            val proof = proofs.find(link.issuer, link.subject)
            if (proof != null) jdbc.sql(
                """INSERT INTO central_account_profile(user_id,issuer,subject,email,display_name,verified_at)
                VALUES(:user,:issuer,:subject,:email,:name,:now) ON CONFLICT(user_id,issuer,subject)
                DO UPDATE SET email=EXCLUDED.email,display_name=EXCLUDED.display_name,verified_at=EXCLUDED.verified_at
                WHERE central_account_profile.verified_at < EXCLUDED.verified_at"""
            )
                .param("user", link.user).param("issuer", link.issuer).param("subject", link.subject)
                .param("email", proof.email, java.sql.Types.VARCHAR)
                .param("name", proof.displayName, java.sql.Types.VARCHAR).param("now", Timestamp.from(proof.verifiedAt))
                .update()
        }
        jdbc.sql("DELETE FROM central_account_profile p WHERE directory_id IS NULL AND NOT EXISTS(SELECT 1 FROM central_identity_link l WHERE l.user_id=p.user_id AND l.issuer=p.issuer AND l.subject=p.subject)")
            .update()
        if (origin == null) return
        val pending = jdbc.sql(
            """SELECT p.*,l.linked_at,u.username,s.id AS installation_id,s.name,s.type
            FROM central_account_profile p LEFT JOIN central_identity_link l
            ON l.user_id=p.user_id AND l.issuer=p.issuer AND l.subject=p.subject
            JOIN user_account u ON u.id=p.user_id JOIN kyrion_space s ON s.id=u.space_id
            WHERE p.last_attempt_at IS NULL OR p.last_attempt_at < CURRENT_TIMESTAMP-interval '30 seconds'
            ORDER BY p.last_attempt_at NULLS FIRST LIMIT 4"""
        ).query { rs, _ ->
            Pending(
                Link(
                    rs.getObject("user_id", UUID::class.java),
                    rs.getString("issuer"),
                    rs.getString("subject"),
                    rs.getTimestamp("linked_at")?.toInstant(),
                    rs.getString("username"),
                    rs.getObject("installation_id", UUID::class.java),
                    rs.getString("name"),
                    rs.getString("type")
                ),
                rs.getObject("directory_id", UUID::class.java),
                rs.getBytes("credential_ciphertext"),
                rs.getBytes("credential_nonce"),
                rs.getTimestamp("synchronized_at")?.toInstant()
            )
        }.list()
        for (entry in pending) {
            if (entry.link.linkedAt != null && entry.synced?.isAfter(Instant.now().minusSeconds(3600)) == true) continue
            val l = entry.link
            try {
                jdbc.sql("UPDATE central_account_profile SET last_attempt_at=CURRENT_TIMESTAMP WHERE user_id=:user AND issuer=:issuer AND subject=:subject")
                    .param("user", l.user).param("issuer", l.issuer).param("subject", l.subject).update()
                val receipt = entry.encrypted?.let { cipher.reveal(ProtectedCredential(it, entry.nonce!!), context(l)) }
                if (l.linkedAt == null) {
                    if (receipt != null) send("DELETE", receipt, mapOf("id" to entry.id.toString()))
                    jdbc.sql("DELETE FROM central_account_profile WHERE user_id=:user AND issuer=:issuer AND subject=:subject")
                        .param("user", l.user).param("issuer", l.issuer).param("subject", l.subject).update()
                    continue
                }
                val body = mapOf(
                    "installationId" to l.installation.toString(),
                    "localUserId" to l.user.toString(),
                    "name" to l.name,
                    "spaceType" to l.type,
                    "localUsername" to l.username,
                    "linkedAt" to l.linkedAt.toString()
                )
                if (receipt != null) {
                    send("PUT", receipt, body + ("id" to entry.id.toString()))
                    markSynced(l)
                } else {
                    val proof = proofs.find(l.issuer, l.subject)?.accessToken ?: continue
                    val result = send("POST", proof, body) ?: continue
                    val id = UUID.fromString(result.path("id").asText())
                    val credential =
                        result.path("credential").asText().takeIf { it.matches(Regex("[A-Za-z0-9_-]{43}")) } ?: continue
                    val protected = cipher.protect(credential, context(l))
                    jdbc.sql(
                        """UPDATE central_account_profile SET directory_id=:id,credential_ciphertext=:cipher,credential_nonce=:nonce,synchronized_at=CURRENT_TIMESTAMP
                        WHERE user_id=:user AND issuer=:issuer AND subject=:subject"""
                    )
                        .param("id", id).param("cipher", protected.ciphertext).param("nonce", protected.nonce)
                        .param("user", l.user).param("issuer", l.issuer).param("subject", l.subject).update()
                }
            } catch (error: Exception) {
                log.warn(
                    "Central installation directory retry: {}",
                    if (error is DirectoryRejected) "HTTP_${error.status}" else "TRANSPORT_OR_RESPONSE"
                )
            }
        }
    }

    private fun markSynced(l: Link) {
        jdbc.sql("UPDATE central_account_profile SET synchronized_at=CURRENT_TIMESTAMP WHERE user_id=:user AND issuer=:issuer AND subject=:subject")
            .param("user", l.user).param("issuer", l.issuer).param("subject", l.subject).update()
    }

    private fun context(l: Link) = "central-directory:${l.user}:${l.issuer}:${l.subject}"
    private fun send(method: String, credential: String, body: Map<String, String>): JsonNode? {
        val request =
            HttpRequest.newBuilder(origin!!.resolve("/api/account/installations/report")).timeout(Duration.ofSeconds(5))
                .header("Authorization", "Bearer $credential").header("Content-Type", "application/json")
                .method(method, HttpRequest.BodyPublishers.ofString(mapper.writeValueAsString(body))).build()
        val limited = LimitedIdentityBody()
        val future = http.sendAsync(request) { limited }
        try {
            val result = future.get(5, TimeUnit.SECONDS)
            if (method == "DELETE" && result.statusCode() == 404) return null
            if (result.statusCode() !in 200..299) throw DirectoryRejected(result.statusCode())
            return if (result.body().isEmpty()) null else mapper.readTree(result.body())
        } finally {
            limited.cancel(); if (!future.isDone) future.cancel(true)
        }
    }

    private class DirectoryRejected(val status: Int) : RuntimeException()

    private data class Link(
        val user: UUID,
        val issuer: String,
        val subject: String,
        val linkedAt: Instant?,
        val username: String,
        val installation: UUID,
        val name: String,
        val type: String
    )

    private data class Pending(
        val link: Link,
        val id: UUID?,
        val encrypted: ByteArray?,
        val nonce: ByteArray?,
        val synced: Instant?
    )
}

@RestController
class CentralAccountController(private val directory: CentralAccountDirectory) {
    @GetMapping("/v1/auth/central/account")
    fun account(request: HttpServletRequest, response: HttpServletResponse): CentralAccountView {
        response.setHeader("Cache-Control", "no-store")
        val token = request.getHeader("Authorization")?.takeIf { it.startsWith("Bearer ") }?.substring(7)
            ?: throw UnauthenticatedException()
        return directory.account(token)
    }
}
