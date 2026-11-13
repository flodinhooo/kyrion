# ADR 0063: Embedded authenticated release-channel bootstrap

Status: Accepted

The downloaded installer must be able to configure regular signed update checks
without asking end users to locate a public trust-store file. Embed an explicitly
provided versioned public channel document in native installer/service-host builds.
It contains only the HTTPS release-index URL and the existing scoped Ed25519 trust
document. Bind its exact bytes to the embedded build identity and build report.
Never synthesize production keys, invent an available feed, or silently trust
keys downloaded from that feed. Development builds may remain explicitly
unconfigured. Production release builds must supply a validated channel.

After local setup, offer notification-only machine scheduling using the existing
protected worker/policy and platform scheduler. Show the feed and trust epoch;
retain explicit configuration consent and an optional skip/continuation path.
Automatic installation remains a separate maintenance-window/key-custody consent.
Do this outside the setup journal lock. Existing changed policies must not be
overwritten: retain the installed feed/trust or use existing explicit disable and
authenticated key-rotation paths. The installer does not host a website wizard,
create accounts/Spaces, publish releases or gain new remote-control endpoints.

An unconfigured or unreleased development package must describe that condition,
not show a successful schedule or a nonexistent public download. Productive
channel/trust configuration remains a release-operator prerequisite; all parsing,
packaging, tamper, scheduling and continuation code must be testable with isolated
public test keys and injected OS registration.
