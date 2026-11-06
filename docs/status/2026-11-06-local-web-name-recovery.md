# Local Web hostname restored

Date: 2026-11-06. The owner requested restoration of the existing local phone
Web access at `https://kyrion-node.local` after the platform update.

## Observed causes and repair

The Windows Ethernet client uses the Pi-hole DNS server on the Pi. Pi-hole's
`dns.hosts` list was empty, and direct queries returned no host record. Avahi's
D-Bus API independently reported the current advertised name as
`kyrion-node-2.local`, rather than the certificate/platform hostname. The older
name-change event was not present in the retained journal; its triggering
conflict was not identified.

A protected on-Pi recovery directory was created at
`/var/backups/kyrion/dns-repair-20261106T103330Z`. It retains the previous
Pi-hole TOML, original DNS host list and Avahi configuration. The existing
Pi-hole v6 CLI was used to add the reserved Ethernet address for
`kyrion-node.local`, preserving other host records, then reload DNS. See the
[official Pi-hole configuration reference](https://docs.pi-hole.net/ftldns/configfile/).
The persisted configuration remains in its existing `/etc/pihole` bind mount.

Only the Avahi service was restarted. Its configuration was not changed;
the new journal and D-Bus API both confirmed `kyrion-node.local`. The Windows
DNS client cache was cleared. No router/DHCP settings, external DNS provider,
client hosts file, IPv6 configuration, keys or certificate trust were changed.

## Verification

- Direct DNS query to the Pi-hole server returned the reserved Pi IPv4 address.
- Normal Windows name resolution returned the correct LAN address records.
- Normal Windows curl to `https://kyrion-node.local/login` returned HTTP200,
  without an explicit address mapping, CA override or insecure flag.
- Avahi reported the original hostname after restart; the startup journal
  confirmed registration.

The local hostname is restored for the LAN DNS and mDNS paths used by the
existing Web access. The actual phone browser and physical device control were
not remotely exercised; the phone must be on the same local network and retain
its previously installed server-certificate trust.

Rollback, if needed: restore the previous `dns.hosts` list through the same
Pi-hole CLI and reload DNS. No Avahi configuration rollback is necessary because
the service configuration was preserved.
