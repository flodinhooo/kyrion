package dev.kyrion.core.security

import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test

class BusinessAddressTest {
    @Test
    fun `domains normalize IDNA and case without implicit subdomains`() {
        assertThat(BusinessAddress.domain(" BÜCHER.ch. ")).isEqualTo("xn--bcher-kva.ch")
        assertThat(BusinessAddress.email(" Member+tag@COMPANY.CH "))
            .isEqualTo("Member+tag@company.ch")
        assertThat(BusinessAddress.domain("subsidiary.company.ch"))
            .isEqualTo("subsidiary.company.ch")
    }

    @Test
    fun `rejects wildcards IPs header injection and malformed addresses`() {
        listOf("*.company.ch", "127.0.0.1", "company..ch", "https://company.ch", "-company.ch")
            .forEach {
                assertThatThrownBy { BusinessAddress.domain(it) }
                    .isInstanceOf(IdentityPolicyException::class.java)
            }
        listOf(
                "x@company.ch\r\nBcc: x@example.com",
                "x@@company.ch",
                ".x@company.ch",
                "a..b@company.ch",
                "x@company.ch/other",
            )
            .forEach {
                assertThatThrownBy { BusinessAddress.email(it) }
                    .isInstanceOf(IdentityPolicyException::class.java)
            }
    }

    @Test
    fun `SMTP absence cannot produce mailbox verification`() {
        val smtp = SmtpVerificationDelivery("", 587, "", "", "")
        assertThat(smtp.available()).isFalse()
        assertThatThrownBy { smtp.send("member@company.ch", "secret") }
            .isInstanceOf(IdentityPolicyException::class.java)
    }
}
