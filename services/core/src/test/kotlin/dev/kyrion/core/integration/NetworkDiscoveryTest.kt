package dev.kyrion.core.integration

import org.junit.jupiter.api.Assertions.*
import org.junit.jupiter.api.Test

class NetworkDiscoveryTest {
    @Test
    fun `scan uses the actual local subnet excluding network and broadcast`() {
        assertEquals(listOf("192.168.1.5", "192.168.1.6"), NetworkDiscoveryRules.hosts("192.168.1.6", 30))
        val hosts = NetworkDiscoveryRules.hosts("192.168.2.30", 23)
        assertEquals(510, hosts.size)
        assertEquals("192.168.2.1", hosts.first())
        assertEquals("192.168.3.254", hosts.last())
        assertTrue(NetworkDiscoveryRules.hosts("10.0.0.1", 8).isEmpty())
        assertThrows(IntegrationInvalidHostException::class.java) { NetworkDiscoveryRules.hosts("8.8.8.8", 24) }
    }

    @Test
    fun `unknown manufacturers are retained and a named discovery enriches an address`() {
        val probe = DiscoveredNetworkDevice("network", "192.168.1.2", "192.168.1.2", 443)
        val printer = probe.copy(name = "Office printer", port = 631)
        assertEquals(printer, NetworkDiscoveryRules.prefer(probe, printer))
        assertEquals(printer, NetworkDiscoveryRules.prefer(printer, probe))
        assertEquals("network", NetworkDiscoveryRules.provider("_ipp._tcp.local.", "printer.local."))
        val shelly = probe.copy(provider = "shelly", name = "Room sensor", port = 80)
        assertEquals(shelly, NetworkDiscoveryRules.prefer(printer, shelly))
        assertEquals("shelly", NetworkDiscoveryRules.provider("_shelly._tcp.local.", "shellyhtg3-abc.local."))
        assertEquals("network", NetworkDiscoveryRules.provider("_shelly._tcp.local.", "shellyplug-abc.local."))
    }

    @Test
    fun `SSDP keeps the responding address and never follows a supplied URL`() {
        val response = "HTTP/1.1 200 OK\r\nSERVER: Living room TV\r\nLOCATION: http://8.8.8.8:8080/description.xml\r\n\r\n"
        assertEquals(DiscoveredNetworkDevice("network", "Living room TV", "192.168.1.2", 8080),
            NetworkAdvertisements.ssdpDevice("192.168.1.2", response))
        assertNull(NetworkAdvertisements.ssdpDevice("8.8.8.8", response))
        assertNull(NetworkAdvertisements.ssdpDevice("192.168.1.2", "invalid"))
    }

    @Test
    fun `HTTP identification includes Shelly devices without granting unsupported devices an adapter`() {
        assertEquals("shelly", NetworkDeviceIdentity.parseShelly("192.168.1.3", """{"id":"shellyhtg3-abc"}""")?.provider)
        assertEquals("network", NetworkDeviceIdentity.parseShelly("192.168.1.3", """{"id":"shellyplug-abc"}""")?.provider)
        assertNull(NetworkDeviceIdentity.parseShelly("192.168.1.3", "<html>Not found</html>"))
        assertNull(NetworkDeviceIdentity.parseShelly("192.168.1.3", "{}"))
    }
}
