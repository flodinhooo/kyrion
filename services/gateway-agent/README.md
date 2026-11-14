# Kyrion Gateway Agent

This directory contains the device-independent Kyrion gateway agent.

The gateway agent will authenticate a managed node with Kyrion Core, report
bounded health and capability information, and execute only typed operations
that Core has authorised. It must not expose unrestricted shell, radio, Home
Assistant, or operating-system access to Web or the AI service.

Version `0.1.0` implements one-time enrollment, protected local credentials,
bounded Linux health collection, authenticated heartbeats and bounded Zigbee
command execution through loopback-only MQTT. Command polling runs separately
from health collection so local commands can normally be claimed within 250 ms
without increasing the five-second full-health cadence. It is deployed as a
hardened systemd service on the first Raspberry Pi node.

The deployed node uses the router-provided local DNS URL
`http://kyrion-core.home:8080` for Core. A stable name keeps DHCP addresses out
of runtime configuration, but it is not an authority boundary: the gateway
continues to authenticate with its protected node identity and token, and Core
remains restricted to the node by the host firewall.

## Prepared verified-TLS enrollment (development source)

Core enrollment protocol 2 supports an interrupted registration acknowledgement
without creating a second node. The Linux agent now offers `enroll-prepared`,
using the same `agent.json`, gateway identity, permissions and runtime commands.
This is developer/operator integration, not completed downloaded-installer node
deployment or a Windows agent implementation.

Run enrollment as the dedicated agent identity with a private 0700 configuration
directory and a 0600 pairing-code file owned by that identity. The code is not a
web-account password and is not supplied as a command argument. A custom local
Core certificate must be obtained through the approved local installer/operator
trust path; no insecure certificate fetch or TLS-verification override exists.

```text
kyrion-gateway-agent --config PRIVATE/agent.json enroll-prepared --core-url https://CORE-IP:PORT --token-file PRIVATE/pairing-code --ca-certificate LOCAL-CORE-CA.pem
kyrion-gateway-agent --config PRIVATE/agent.json enroll-prepared
```

The second form resumes the protected pending request after interruption. It
reuses its original identity/version and credential. A committed final config
can finish pending cleanup without another network request. Existing configured
identities are never silently replaced. Expired/rejected pending claims remain
preserved for explicit authorized recovery; automatic re-pairing is not offered.
Core protocol capability is checked before transmitting the pairing code. Legacy
servers cannot accidentally consume a code while ignoring the new credential.

Prepared mode requires verified HTTPS, rejects redirects/proxies and connects
only to checked RFC1918 IPv4, IPv4 loopback, IPv6 ULA or IPv6 loopback addresses.
It resolves once per connection, connects the checked numeric socket and verifies
its peer plus TLS hostname. Mixed/public DNS answers are refused. Global IPv6,
link-local addresses and public remote access are not supported by this path.
Selected CA bytes are copied privately and pinned by SHA-256 for later requests;
no new runtime dependency is required. Legacy explicit HTTP configuration remains
compatible and is not automatically rewritten or deployed by source changes.

The checked-in unit now bounds process crash restarts to three per five minutes.
Normal Core-disconnection backoff/reconnection remains separate. Installing this
service identity/unit and the complete installer task/role workflow remain
separate work; no existing host account or service was changed by these commits.
