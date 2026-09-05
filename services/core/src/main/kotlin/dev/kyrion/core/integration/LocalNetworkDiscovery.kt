package dev.kyrion.core.integration

import org.springframework.stereotype.Component
import java.net.Inet4Address
import java.net.InetAddress
import java.net.NetworkInterface
import java.net.InetSocketAddress
import java.net.Socket
import java.util.concurrent.Callable
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

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
    @Synchronized
    override fun discover(): List<DiscoveredNetworkDevice> {
        val interfaces = NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback && !it.isVirtual && !it.isPointToPoint }
            .flatMap { it.interfaceAddresses }.filter { it.address is Inet4Address && it.address.isSiteLocalAddress }
        if (interfaces.isEmpty()) throw java.io.IOException("No local IPv4 interface")
        val found = ConcurrentHashMap<String, DiscoveredNetworkDevice>()
        fun accept(device: DiscoveredNetworkDevice) {
            found.compute(device.host) { _, previous -> NetworkDiscoveryRules.prefer(previous, device) }
        }
        val workers = Executors.newFixedThreadPool(64)
        try {
            val tasks = interfaces.take(8).flatMap { iface -> listOf(
                Callable { NetworkAdvertisements.mdns(iface.address, ::accept) },
                Callable { NetworkAdvertisements.ssdp(iface.address, ::accept) },
            ) }.toMutableList()
            val ownAddresses = interfaces.map { it.address.hostAddress }.toSet()
            interfaces.flatMap { NetworkDiscoveryRules.hosts(it.address.hostAddress, it.networkPrefixLength.toInt()) }
                .distinct().filterNot { it in ownAddresses }.take(4096).forEach { host ->
                    tasks.add(Callable { probe(host)?.let(::accept); Unit })
                }
            workers.invokeAll(tasks, 15, TimeUnit.SECONDS)
        } finally {
            workers.shutdownNow()
        }
        return found.values.sortedWith(compareBy({ it.name == it.host }, { it.name.lowercase() })).take(512)
    }

    private fun probe(host: String): DiscoveredNetworkDevice? {
        for (port in listOf(80, 443, 22, 445, 8080, 8008, 554, 16021)) {
            if (Thread.currentThread().isInterrupted) return null
            try {
                Socket().use { it.connect(InetSocketAddress(host, port), 150) }
                return DiscoveredNetworkDevice("network", host, host, port)
            } catch (_: java.io.IOException) { /* Try the next common local service. */ }
        }
        return try {
            if (InetAddress.getByName(host).isReachable(200)) DiscoveredNetworkDevice("network", host, host, 0) else null
        } catch (_: java.io.IOException) { null }
    }
}

object NetworkDiscoveryRules {
    fun hosts(host: String, prefix: Int): List<String> {
        privateNetworkIpv4(host)
        // Larger directly connected networks still participate in multicast discovery.
        if (prefix !in 20..30) return emptyList()
        val value = host.split('.').fold(0L) { total, octet -> (total shl 8) or octet.toLong() }
        val size = 1L shl (32 - prefix)
        val network = value and (0xffffffffL xor (size - 1))
        return (network + 1 until network + size - 1).map { address ->
            (3 downTo 0).joinToString(".") { ((address shr (it * 8)) and 255).toString() }
        }.filter { try { privateNetworkIpv4(it); true } catch (_: IntegrationInvalidHostException) { false } }
    }

    fun provider(type: String, name: String): String = when {
        type.equals("_nanoleafapi._tcp.local.", true) -> "nanoleaf"
        name.lowercase().startsWith("shellyhtg3-") || name.lowercase().startsWith("shellyplusht-") -> "shelly"
        else -> "network"
    }

    fun prefer(previous: DiscoveredNetworkDevice?, candidate: DiscoveredNetworkDevice): DiscoveredNetworkDevice {
        if (previous == null) return candidate
        fun score(device: DiscoveredNetworkDevice) = (if (device.provider != "network") 2 else 0) + (if (device.name != device.host) 1 else 0)
        return if (score(candidate) > score(previous)) candidate else previous
    }
}
