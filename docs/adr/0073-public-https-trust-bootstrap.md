# ADR 0073: Public HTTPS trust bootstrap without disabling TLS

Status: Accepted for implementation, 2026-11-14.

A minimal target may have no OS CA store before the installer can obtain its
signed release metadata. Keep TLS hostname/certificate verification mandatory.
Vendor only the unchanged public Mozilla CA data and license from the reviewed
Certifi 2026.10.23 wheel, not its Python package. This adds no executable/runtime
dependency and never copies private/enterprise CAs from the build machine.
Pin wheel and extracted bundle hashes, record provenance/license and include the
resources in the existing source snapshot/native package. Updating this trust
data is an explicit reviewed source/release change.

Use the OS trust context first for public release/model metadata and artifact
downloads. Honor explicitly configured SSL_CERT_FILE/SSL_CERT_DIR and existing
system certificate files/hashed CA directories. Only when those defaults are
absent and no CA is loaded may the public transport load the pinned bundle.
Never retry a failed certificate or hostname check through a weaker context,
follow new redirects, modify the OS trust store or widen pinned local Core TLS.
The embedded release-index/model signing authority remains independent and
mandatory; a valid public TLS chain is not a signed Kyrion release.

Expose only local trust/resource diagnostics through existing installer
capabilities; those facts are not a network-success claim. Tests cover actual
missing-store HTTPS in a marked minimal Debian chroot, invalid chains/hostnames,
tampered resources and explicit trust overrides. Native resource/context probes
and source HTTPS tests remain distinguishable from full installer acceptance.

Official provenance checked 2026-11-14:
[Certifi on PyPI](https://pypi.org/project/certifi/2026.10.23/) and
[upstream trust-data policy](https://github.com/certifi/python-certifi).
Wheel SHA-256:
`e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1`.
