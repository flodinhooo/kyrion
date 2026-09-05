package dev.kyrion.core.integration

import org.springframework.stereotype.Component
import java.net.Inet4Address
import java.net.InetAddress
import javax.jmdns.JmDNS

data class DiscoveredNetworkDevice(val provider: String, val name: String, val host: String, val port: Int)

fun privateNetworkIpv4(value: String): String {
    if (!value.matches(Regex("(?:[0-9]{1,3}\\.){3}[0-9]{1,3}"))) throw IntegrationInvalidHostException()
    val octets = value.split('.').map { it.toInt() }
    if (octets.any { it !in 0..255 }) throw IntegrationInvalidHostException()
    val address = InetAddress.getByAddress(octets.map { it.toByte() }.toByteArray())
    if (address !is Inet4Address || !address.isSiteLocalAddress) throw IntegrationInvalidHostException()
    return address.hostAddress
}

interface LocalNetworkDiscovery {
    fun discover(): List<DiscoveredNetworkDevice>
}

@Component
class MdnsLocalNetworkDiscovery : LocalNetworkDiscovery {
    override fun discover(): List<DiscoveredNetworkDevice> = JmDNS.create().use { mdns ->
        // Register both queries before waiting so providers share the discovery window.
        TYPES.keys.forEach { mdns.registerServiceType(it) }
        TYPES.flatMap { (type, provider) ->
            mdns.list(type, 3000).flatMap { service ->
                service.inet4Addresses.mapNotNull { address ->
                    val host = try { privateNetworkIpv4(address.hostAddress) } catch (_: IntegrationInvalidHostException) { return@mapNotNull null }
                    val port = if (provider == "nanoleaf") 16021 else 80
                    if (service.port != port) return@mapNotNull null
                    DiscoveredNetworkDevice(provider, service.name.take(160), host, port)
                }
            }
        }.distinctBy { it.provider to it.host }.sortedBy { it.name.lowercase() }.take(100)
    }

    companion object {
        val TYPES = mapOf("_nanoleafapi._tcp.local." to "nanoleaf", "_shelly._tcp.local." to "shelly")
    }
}
