# Local network discovery and Shelly H&T

## Implemented scope

The Add Device screen searches for local devices independently of manufacturer using
`POST /v1/integrations/network/discover`. Discovery is owner-authenticated and
initiated explicitly through the CSRF-protected Web route. It combines dynamic
mDNS service-type browsing, SSDP discovery and TCP/ICMP reachability probes on
directly connected private IPv4 networks. Advertised printers, computers,
media devices and devices without a Kyrion integration remain visible.
Results are merged by IP address, preferring named advertisements over a bare
address. An HTTP `/shelly` identity check also recognises awake Shelly devices
without mDNS. Discovery advertisements are hints, not authorisation or proof
of a supported device.

The UI shows one search button and a compact name/IP list. Per-device details
and supported connection actions are collapsed initially. Unintegrated devices
are visible with an explanation when expanded. There is no provider-specific
manual-address form or permanent setup text on this screen.

Discovery results include an owner-scoped `connected` flag for matching stored
Nanoleaf/Shelly endpoints. Web labels those results Already connected and links
to Devices instead of offering pairing again. Another owner's connection never
affects this flag. Matching currently uses the saved IP and provider, so DHCP
reconciliation remains a separate limitation.

Discovery uses active, non-loopback, non-virtual, non-point-to-point interfaces.
The active sweep covers actual subnet prefixes from /20 through /30, with up to
4096 candidate addresses, 64 workers and a 15-second shared deadline; multicast
browsing also runs on larger networks (up to eight interface addresses).
TCP probes use ports 80, 443, 22, 445, 8080, 8008, 554 and 16021, then ICMP.
These bounds prevent unbounded scanning; results are not an inventory guarantee
for large networks, firewalled or sleeping devices, other VLANs or IPv6-only
devices. At most 512 results are returned. Supplied SSDP URLs are never fetched.

Nanoleaf keeps its existing physical authorisation flow. Shelly candidates can
be explicitly added by expanding their result.
Core verifies `Shelly.GetDeviceInfo` (HT application, generation 2 or 3), then
reads `Shelly.GetStatus`. The supported read-only slice is Shelly Plus H&T and
H&T Gen3 with unauthenticated local RPC. Password-protected devices receive an
explicit `SHELLY_AUTH_REQUIRED` error; Kyrion never disables device protection.
Gen1, BLU H&T and other Shelly products are not supported by this adapter.

Core persists owner-scoped connections and the latest temperature in Celsius,
relative humidity and optional battery percentage. Flyway V24 adds the reading
table; deletion of a connection cascades to its reading. No device credentials
are needed for this slice. Adding requires `confirmed: true` and produces an
owner-scoped activity event. Existing room assignment, naming and confirmed
connection removal are available from Devices.

The catalog exposes `temperature.read`, `humidity.read` and `battery.read`;
state has nullable `temperatureCelsius`, `relativeHumidity` and `measuredAt`
fields. `measuredAt` records Core's successful retrieval time, not a fabricated
device measurement timestamp. Web renders these provider-neutral fields with
German and English labels. UI and AI never call a device directly.

## Operating the sensor

1. Connect the sensor to the same Wi-Fi network using its local setup interface.
2. Briefly press its button to wake it for setup, discovery and connection.
3. In Kyrion, open Devices > Add device > Local network and start discovery.
4. Add the sensor explicitly, then open Devices to name it, assign a room and
   view its readings. Use the existing status refresh while the device is awake
   to retrieve another reading.

Sleeping H&T devices may be unreachable even when powered by USB. A failed
read preserves the previous values and retrieval timestamp; reachability is
unknown, rather than an assertion that the sensor is broken. Catalog reads
are passive. Automatic wake-period ingestion through MQTT or outbound
WebSocket is follow-up work, as are password support and DHCP reconciliation.
No continuous monitoring is claimed by this manual-refresh slice.

## Verification boundary

Automated coverage exercises protocol parsing, private-address validation,
confirmation, owner isolation, duplicate connection reuse, preservation during
sleep and Web response contracts. A local network smoke test on 2026-09-05
returned nine devices (two Nanoleafs and seven other devices) in approximately
eight seconds. Shelly discovery and readings still require verification against
the owner's awake sensor; none was identified during this scan.

Protocol references: [Shelly mDNS](https://shelly-api-docs.shelly.cloud/gen2/General/mDNS/),
[Shelly RPC](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Shelly/),
[H&T Gen3](https://shelly-api-docs.shelly.cloud/gen2/Devices/Gen3/ShellyHTG3/),
and [wake-up behaviour](https://support.shelly.cloud/en/support/solutions/articles/103000226308-wake-up-schemes-and-data-reporting-for-shelly-plus-h-t-and-shelly-gen3-h-t-devices).
