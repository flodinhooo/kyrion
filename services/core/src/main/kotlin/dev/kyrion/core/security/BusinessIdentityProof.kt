package dev.kyrion.core.security

import java.net.IDN
import java.util.Hashtable
import javax.naming.directory.InitialDirContext
import org.springframework.beans.factory.annotation.Value
import org.springframework.context.annotation.Configuration
import org.springframework.context.annotation.PropertySource
import org.springframework.mail.SimpleMailMessage
import org.springframework.mail.javamail.JavaMailSenderImpl
import org.springframework.stereotype.Component

@Configuration
@PropertySource("classpath:identity/smtp.properties")
class BusinessIdentityConfiguration

object BusinessAddress {
    fun domain(value: String): String {
        val raw = value.trim().removeSuffix(".")
        val domain =
            runCatching { IDN.toASCII(raw, IDN.USE_STD3_ASCII_RULES).lowercase() }
                .getOrElse { throw IdentityPolicyException("DOMAIN_INVALID") }
        if (
            domain.length !in 3..253 ||
                !domain.contains('.') ||
                domain.split('.').any {
                    it.length !in 1..63 || !it.matches(Regex("[a-z0-9](?:[a-z0-9-]*[a-z0-9])?"))
                } ||
                domain.split('.').all { it.all(Char::isDigit) }
        )
            throw IdentityPolicyException("DOMAIN_INVALID")
        return domain
    }

    fun email(value: String): String {
        val parts = value.trim().split('@')
        if (
            parts.size != 2 ||
                parts[0].length !in 1..64 ||
                !parts[0].matches(Regex("[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+")) ||
                parts[0].startsWith('.') ||
                parts[0].endsWith('.') ||
                parts[0].contains("..")
        )
            throw IdentityPolicyException("EMAIL_INVALID")
        // Preserve local-part case: SMTP local parts need not be case insensitive.
        return "${parts[0]}@${domain(parts[1])}"
            .also { if (it.length > 254) throw IdentityPolicyException("EMAIL_INVALID") }
    }
}

fun interface DomainTxtLookup {
    fun records(domain: String): List<String>
}

@Component
class JndiDomainTxtLookup(
    @Value("\${kyrion.identity.dns.server:}") private val server: String = ""
) : DomainTxtLookup {
    override fun records(domain: String): List<String> {
        val context =
            InitialDirContext(
                Hashtable<String, String>().apply {
                    put("java.naming.factory.initial", "com.sun.jndi.dns.DnsContextFactory")
                    put("com.sun.jndi.dns.timeout.initial", "2000")
                    put("com.sun.jndi.dns.timeout.retries", "1")
                    if (server.isNotBlank()) {
                        val uri = java.net.URI(server)
                        require(
                            uri.scheme == "dns" &&
                                uri.host != null &&
                                uri.userInfo == null &&
                                uri.query == null &&
                                uri.fragment == null
                        )
                        require(uri.path.isNullOrEmpty() || uri.path == "/")
                        put("java.naming.provider.url", server)
                    }
                }
            )
        return try {
            val records =
                context
                    .getAttributes(
                        "_kyrion-verification.${BusinessAddress.domain(domain)}",
                        arrayOf("TXT"),
                    )
                    .get("TXT") ?: return emptyList()
            (0 until records.size()).take(64).map { index ->
                records.get(index).toString().take(4096).let { value ->
                    // JNDI separates RR character strings with spaces and only quotes
                    // segments that need quoting. Preserve spaces inside quoted segments.
                    val parts = Regex("\"([^\"\\\\]*)\"|([^\\s\"\\\\]+)").findAll(value).toList()
                    var cursor = 0
                    val decoded = StringBuilder()
                    var valid = true
                    parts.forEach { part ->
                        if (!value.substring(cursor, part.range.first).all(Char::isWhitespace))
                            valid = false
                        decoded.append(part.groupValues[1].ifEmpty { part.groupValues[2] })
                        cursor = part.range.last + 1
                    }
                    if (!value.substring(cursor).all(Char::isWhitespace)) valid = false
                    if (valid) decoded.toString() else value
                }
            }
        } finally {
            context.close()
        }
    }
}

interface VerificationDelivery {
    fun available(): Boolean

    fun send(email: String, token: String)
}

@Component
class SmtpVerificationDelivery(
    @Value("\${kyrion.identity.smtp.host:}") private val host: String,
    @Value("\${kyrion.identity.smtp.port:587}") private val port: Int,
    @Value("\${kyrion.identity.smtp.username:}") private val username: String,
    @Value("\${kyrion.identity.smtp.password:}") private val password: String,
    @Value("\${kyrion.identity.smtp.from:}") private val from: String,
) : VerificationDelivery {
    override fun available() = host.isNotBlank() && from.isNotBlank()

    override fun send(email: String, token: String) {
        if (!available()) throw IdentityPolicyException("SMTP_UNAVAILABLE")
        val sender =
            JavaMailSenderImpl().apply {
                host = this@SmtpVerificationDelivery.host
                port = this@SmtpVerificationDelivery.port
                username = this@SmtpVerificationDelivery.username
                password = this@SmtpVerificationDelivery.password
                javaMailProperties.setProperty("mail.debug", "false")
                javaMailProperties.setProperty(
                    "mail.smtp.auth",
                    this@SmtpVerificationDelivery.username.isNotBlank().toString(),
                )
                javaMailProperties.setProperty("mail.smtp.starttls.enable", "true")
                javaMailProperties.setProperty("mail.smtp.starttls.required", "true")
                javaMailProperties.setProperty("mail.smtp.ssl.checkserveridentity", "true")
                javaMailProperties.setProperty("mail.smtp.connectiontimeout", "10000")
                javaMailProperties.setProperty("mail.smtp.timeout", "10000")
                javaMailProperties.setProperty("mail.smtp.writetimeout", "10000")
            }
        val template =
            javaClass
                .getResourceAsStream("/identity/email-verification.txt")!!
                .bufferedReader()
                .use { it.readText() }
        try {
            sender.send(
                SimpleMailMessage().apply {
                    setFrom(BusinessAddress.email(this@SmtpVerificationDelivery.from))
                    setTo(email)
                    subject = "Kyrion — E-Mail / email verification"
                    text = template.replace("{code}", token)
                }
            )
        } catch (_: Exception) {
            throw IdentityPolicyException("SMTP_UNAVAILABLE")
        }
    }
}

class IdentityPolicyException(val code: String) : RuntimeException()
