package dev.kyrion.core.integration

import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.SocketTimeoutException
import java.net.URI
import java.util.concurrent.ConcurrentHashMap
import javax.jmdns.JmDNS
import javax.jmdns.ServiceEvent
import javax.jmdns.ServiceListener
import javax.jmdns.ServiceTypeListener

object NetworkAdvertisements {
    fun mdns(address: InetAddress, accept: (DiscoveredNetworkDevice) -> Unit) {
        try {
            JmDNS.create(address).use { mdns ->
                val types = ConcurrentHashMap.newKeySet<String>()
                val listener = object : ServiceListener {
                    override fun serviceAdded(event: ServiceEvent) { mdns.requestServiceInfo(event.type, event.name, true, 1000) }
                    override fun serviceRemoved(event: ServiceEvent) = Unit
                    override fun serviceResolved(event: ServiceEvent) {
                        event.info.inet4Addresses.forEach { ip ->
                            val host = try { privateNetworkIpv4(ip.hostAddress) } catch (_: IntegrationInvalidHostException) { return@forEach }
                            val provider = NetworkDiscoveryRules.provider(event.type, event.info.server)
                            accept(DiscoveredNetworkDevice(provider, event.name.take(160), host, event.info.port))
                        }
                    }
                }
                fun listen(type: String) {
                    if (types.size < 128 && types.add(type)) mdns.addServiceListener(type, listener)
                }
                mdns.addServiceTypeListener(object : ServiceTypeListener {
                    override fun serviceTypeAdded(event: ServiceEvent) = listen(event.type)
                    override fun subTypeForServiceTypeAdded(event: ServiceEvent) = listen(event.type)
                })
                // Seed common types as some devices do not answer the service-type enumeration query.
                listOf("_http", "_https", "_ssh", "_smb", "_ipp", "_ipps", "_googlecast", "_airplay", "_raop",
                    "_hap", "_matter", "_shelly", "_nanoleafapi").forEach { listen("$it._tcp.local.") }
                Thread.sleep(4500)
            }
        } catch (_: InterruptedException) { Thread.currentThread().interrupt() }
        catch (_: java.io.IOException) { /* Other discovery methods remain available. */ }
    }

    fun ssdp(address: InetAddress, accept: (DiscoveredNetworkDevice) -> Unit) {
        try {
            DatagramSocket(InetSocketAddress(address, 0)).use { socket ->
                socket.soTimeout = 250
                val bytes = "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\nST: ssdp:all\r\n\r\n".toByteArray(Charsets.US_ASCII)
                socket.send(DatagramPacket(bytes, bytes.size, InetAddress.getByName("239.255.255.250"), 1900))
                val deadline = System.nanoTime() + 3_000_000_000L
                while (System.nanoTime() < deadline && !Thread.currentThread().isInterrupted) {
                    val packet = DatagramPacket(ByteArray(8192), 8192)
                    try { socket.receive(packet) } catch (_: SocketTimeoutException) { continue }
                    ssdpDevice(packet.address.hostAddress, String(packet.data, 0, packet.length, Charsets.UTF_8))?.let(accept)
                }
            }
        } catch (_: java.io.IOException) { /* Other discovery methods remain available. */ }
    }

    fun ssdpDevice(host: String, response: String): DiscoveredNetworkDevice? {
        try { privateNetworkIpv4(host) } catch (_: IntegrationInvalidHostException) { return null }
        if (!response.startsWith("HTTP/1.1 200")) return null
        val headers = response.lineSequence().drop(1).mapNotNull { line ->
            val separator = line.indexOf(':')
            if (separator < 1) null else line.take(separator).trim().lowercase() to line.drop(separator + 1).trim()
        }.toMap()
        val location = try { URI(headers["location"] ?: return null) } catch (_: Exception) { return null }
        // Never follow URLs supplied by a device or resolve their hostnames.
        val port = if (location.port in 1..65535) location.port else if (location.scheme == "https") 443 else 80
        val name = headers["server"]?.takeIf { it.isNotBlank() }?.take(160) ?: host
        return DiscoveredNetworkDevice("network", name, host, port)
    }
}
