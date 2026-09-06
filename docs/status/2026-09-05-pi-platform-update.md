# Pi platform update — 2026-09-05

The owner ran the staged privileged activation script. Subsequent SSH and
HTTPS checks confirmed the new application images on the existing Pi:

- `kyrion/core:pi-20260905t140134z`: healthy;
- `kyrion/web:pi-20260905t140134z`: healthy;
- existing PostgreSQL: healthy, not recreated;
- existing Caddy image: healthy after the healthcheck correction below;
- gateway agent service: active;
- `https://kyrion-node.local/login`: HTTP 200 with certificate verification;
- HTTPS favicon/static asset: HTTP 200.

The activation completion marker is
`/home/flodinho/kyrion-updates/pi-20260905t140134z/activated-version.txt`.
It is written only after verifying the running Core/Web image IDs and health.

## Recovery artifacts

The protected backup is
`/var/backups/kyrion/platform-pi-20260905t140134z-20260905T143817Z`.
It includes the database dump, dump table of contents, original platform
environment/Compose configuration, keys and previous image IDs. The database
dump was verified to exist (approximately 260 KiB, root-only permissions).
Previous application images retain the `rollback-pi-20260905t140134z` tags.
No development database or credentials replaced the Pi's persistent data.

## Caddy healthcheck correction

The pre-existing Caddy container reported TLS handshake errors when its
healthcheck requested `https://127.0.0.1/`. Actual HTTPS requests to
`kyrion-node.local` succeeded. The healthcheck now uses
`https://kyrion-node.local/login`, with that hostname mapped to loopback only
inside the Caddy container. The existing certificate-check behavior of this
internal probe is unchanged; the separate external HTTPS check validates the
certificate normally.

The runtime Compose file was backed up as `compose.before-healthcheck.yml`
inside the recovery directory, validated, then only Caddy was recreated.
The repository Compose file contains the same fix. Core, Web, PostgreSQL and
the gateway remained running during this correction.

These checks verify deployment and service reachability. They do not claim
owner-observed physical light operation or Spotify receiver playback.
