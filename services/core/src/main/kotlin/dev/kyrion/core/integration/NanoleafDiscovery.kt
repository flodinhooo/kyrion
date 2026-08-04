package dev.kyrion.core.integration

import javax.jmdns.JmDNS
import org.springframework.stereotype.Component
import java.time.Duration

data class DiscoveredNanoleaf(val name: String, val host: String, val port: Int)

interface NanoleafDiscovery {
    fun discover(timeout: Duration = Duration.ofSeconds(3)): List<DiscoveredNanoleaf>
}

@Component
class MdnsNanoleafDiscovery : NanoleafDiscovery {
    override fun discover(timeout: Duration): List<DiscoveredNanoleaf> = try {
        JmDNS.create().use { mdns ->
            mdns.list(SERVICE_TYPE, timeout.toMillis()).flatMap { service ->
                service.inet4Addresses.map { address -> DiscoveredNanoleaf(service.name, address.hostAddress, service.port) }
            }.filter { it.port == NANOLEAF_PORT }.distinctBy { it.host }.sortedBy { it.name.lowercase() }
        }
    } catch (_: Exception) { emptyList() }

    companion object {
        const val SERVICE_TYPE = "_nanoleafapi._tcp.local."
        const val NANOLEAF_PORT = 16021
    }
}
