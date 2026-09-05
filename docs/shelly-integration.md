# Local network discovery and Shelly H&T

## Implemented scope

The Add Device screen searches for Nanoleaf and Shelly advertisements using
`POST /v1/integrations/network/discover`. Discovery is owner-authenticated and
initiated explicitly through the CSRF-protected Web route. It queries
`_nanoleafapi._tcp.local.` and `_shelly._tcp.local.` with bounded discovery
windows, restricts candidates to private IPv4 and the expected ports, and
returns provider-tagged candidates. Discovery advertisements are hints, not
authorisation or proof of a supported device.

Nanoleaf keeps its existing physical authorisation flow. Shelly candidates can
be explicitly added from the results, with a manual private IPv4 fallback.
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
3. In Kyrion, open Devices > Add device > Local network and start discovery,
   or enter its private IPv4 address manually.
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
sleep and Web response contracts. Real-device discovery and readings still
require verification against the owner's awake sensor.

Protocol references: [Shelly mDNS](https://shelly-api-docs.shelly.cloud/gen2/General/mDNS/),
[Shelly RPC](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Shelly/),
[H&T Gen3](https://shelly-api-docs.shelly.cloud/gen2/Devices/Gen3/ShellyHTG3/),
and [wake-up behaviour](https://support.shelly.cloud/en/support/solutions/articles/103000226308-wake-up-schemes-and-data-reporting-for-shelly-plus-h-t-and-shelly-gen3-h-t-devices).
