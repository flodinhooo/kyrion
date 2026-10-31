package dev.kyrion.core.security

import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.ServerSocket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import org.assertj.core.api.Assertions.assertThat
import org.assertj.core.api.Assertions.assertThatThrownBy
import org.junit.jupiter.api.Test

class IdentityTransportTest {
    @Test
    fun `SMTP without STARTTLS cannot receive AUTH or message data`() {
        ServerSocket(0, 1, InetAddress.getByName("127.0.0.1")).use { server ->
            val executor = Executors.newSingleThreadExecutor()
            val commands = java.util.concurrent.CopyOnWriteArrayList<String>()
            try {
                val future =
                    executor.submit {
                        server.accept().use { client ->
                            client.soTimeout = 5000
                            val writer = client.getOutputStream().bufferedWriter()
                            fun reply(value: String) {
                                writer.write(value)
                                writer.flush()
                            }
                            reply("220 fixture ESMTP\r\n")
                            val reader = client.getInputStream().bufferedReader()
                            while (true) {
                                val line = reader.readLine() ?: break
                                commands.add(line)
                                if (line.startsWith("EHLO"))
                                    reply("250-fixture\r\n250 AUTH PLAIN\r\n")
                                else if (line == "QUIT") {
                                    reply("221 bye\r\n")
                                    break
                                } else reply("500 unsupported\r\n")
                            }
                        }
                    }
                val smtp =
                    SmtpVerificationDelivery(
                        "127.0.0.1",
                        server.localPort,
                        "fixture",
                        "synthetic-password",
                        "verify@example.invalid",
                    )
                assertThatThrownBy { smtp.send("member@example.invalid", "V".repeat(43)) }
                    .isInstanceOf(IdentityPolicyException::class.java)
                future.get(10, TimeUnit.SECONDS)
                assertThat(commands).anyMatch { it.startsWith("EHLO") }
                assertThat(commands).noneMatch {
                    it.startsWith("AUTH") ||
                        it == "DATA" ||
                        it.contains("synthetic-password") ||
                        it.contains("V".repeat(43))
                }
            } finally {
                executor.shutdownNow()
            }
        }
    }

    @Test
    fun `DNS TXT adapter combines character strings from a real loopback DNS response`() {
        DatagramSocket(0, InetAddress.getByName("127.0.0.1")).use { server ->
            val expected = "kyrion-space=fixture;token=" + "Q".repeat(43)
            val executor = Executors.newSingleThreadExecutor()
            try {
                server.soTimeout = 5000
                val future =
                    executor.submit {
                        val packet = DatagramPacket(ByteArray(2048), 2048)
                        server.receive(packet)
                        val request = packet.data
                        var end = 12
                        while (request[end].toInt() != 0) end += (request[end].toInt() and 255) + 1
                        end += 5
                        val payload = ByteArrayOutputStream()
                        DataOutputStream(payload).use { out ->
                            out.write(request, 0, 2)
                            out.writeShort(0x8180)
                            out.writeShort(1)
                            out.writeShort(1)
                            out.writeShort(0)
                            out.writeShort(0)
                            out.write(request, 12, end - 12)
                            out.writeShort(0xc00c)
                            out.writeShort(16)
                            out.writeShort(1)
                            out.writeInt(60)
                            val parts =
                                listOf(expected.take(20), expected.drop(20)).map {
                                    it.toByteArray(Charsets.US_ASCII)
                                }
                            out.writeShort(parts.sumOf { it.size + 1 })
                            parts.forEach {
                                out.writeByte(it.size)
                                out.write(it)
                            }
                        }
                        val bytes = payload.toByteArray()
                        server.send(DatagramPacket(bytes, bytes.size, packet.address, packet.port))
                    }
                val dns = JndiDomainTxtLookup("dns://127.0.0.1:${server.localPort}/")
                assertThat(dns.records("company.invalid")).contains(expected)
                future.get(10, TimeUnit.SECONDS)
            } finally {
                executor.shutdownNow()
            }
        }
    }
}
