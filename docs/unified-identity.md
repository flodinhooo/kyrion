# Central and local Kyrion accounts

The central account is optional. Existing local users retain their usernames,
Argon2id credentials, sessions, membership and roles. Enabling central login does
not enroll or migrate anyone. [ADR 0041](adr/0041-optional-central-identity.md)
records the provider and deployment decision.

For current deployment observations, use the
[2026-11-12 website acceptance](status/2026-11-12-website-acceptance.md). The
public website account flag and HTTPS discovery are observable independently
from installation Core opt-ins. They do not prove registration, recovery,
website sessions or an authorized local account link. The original loopback pilot
and later public transport/SMTP evidence are dated stages, not competing current
deployment descriptions.

## Ownership and identifiers

| Data                                                         | Authority                           | Transfer                                           |
| ------------------------------------------------------------ | ----------------------------------- | -------------------------------------------------- |
| Central subject, authentication methods, verified email      | Keycloak                            | Only issuer and subject imported into a local link |
| Website account/session                                      | Separate central website PostgreSQL | No local database access                           |
| Local username and password                                  | Local Core                          | Never sent to Keycloak or website                  |
| Space membership, roles, permissions                         | Local Core                          | Never inferred from central claims                 |
| Devices, automations, documents, reminders and other content | Local installation                  | No identity synchronization                        |

`(issuer, subject)` is the external identity key, unique per local database. A
local user has at most one central link. Equal email addresses or usernames are
irrelevant. Providers may issue pairwise subjects for different clients: the
website's subject is not assumed equal to a local client's subject. There is no
cross-client identity join or invented global-account claim.

## Supported flows

1. **Local only:** use the existing protected first-owner setup or an invitation,
   choose “Only use locally”, and log in with the local password. Neither
   provider configuration nor internet access is required.
2. **Connect:** log in locally, open Profile / Link account, enter the current local
   password and explicitly start linking. Enter the code on the website Account /
   Link account tab and approve it at the configured provider. The local UI
   completes the approved link automatically. The current local session must remain
   valid throughout. Codes/operations expire, are one-use and cannot switch user
   or local session. A restart abandons pending operations.
3. **Central login:** authorize a fresh device code and confirm. Only an existing
   mapping to an enabled user with active local membership admits a local session.
   Unknown identities receive `SPACE_ACCESS_REQUIRED`; first use the existing
   protected setup/invitation to establish a password-protected local account,
   then link. No central login or email claim grants OWNER or membership.
4. **Disconnect:** enter the local password and explicitly request removal.
   Central-created sessions are revoked; the local password and all memberships
   survive, including the last OWNER's local access. When disconnecting from a
   central session, log in again locally afterward.

The local device grant is RFC 8628, not authorization code with a special relay.
The provider displays the user code and obtains confirmation; the device code
stays in bounded Core memory. No incoming callback, public installation URL,
dynamic LAN redirect registration or shared local client secret is supported.
Only the website uses authorization code + PKCE S256 with state and nonce and an
exact callback URI. Tokens are never general Core API credentials.

## Website customer experience

The website offers browser registration and an account menu in the header.
Keycloak owns email/password entry, mailbox verification, recovery and account
settings. Website sessions can be remembered for up to 30 days, with encrypted
server-side online renewal and short proof validity. [ADR 0051](adr/0051-customer-website-accounts.md)
supersedes the original website-only short-session restriction. This does not
extend local Core sessions or replace explicit local account linking.

## Expiry, logout and blocking

Local session validation reads only local persistence. A provider outage prevents
new central proofs, not local password login or existing authorized requests.
Local Core sessions created through central sign-in expire within 15 minutes and no later than the ID token expiry;
there is no automatic refresh or indefinite offline extension. A new provider
authorization is required afterward. Central token sets are discarded after
identity validation. The development provider's five-minute token lifetime can
make actual sessions shorter than 15 minutes.

- Session logout revokes the selected relying-party session; it does not disable
  accounts, unlink identities or terminate every provider/browser SSO session.
- Blocking the central account stops new provider authentication. An already
  issued offline local session can persist until its bounded expiry. Immediate
  global/back-channel revocation is not implemented.
- Blocking the local account or suspending its local membership denies local
  access through the existing per-request Core checks, regardless of central state.
- Removing the link prevents future central login and revokes its local central
  sessions while retaining password login and current locally created sessions.

## Local Core configuration

Disabled is the default. For the isolated development provider, set process
environment on a **separate development Core and database**, not the running
installation:

```text
KYRION_CENTRAL_ENABLED=true
KYRION_CENTRAL_ISSUER=http://localhost:8089/realms/kyrion
KYRION_CENTRAL_CLIENT_ID=kyrion-local
KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP=true
```

Production requires an exact HTTPS issuer without trailing slash and
`KYRION_CENTRAL_ALLOW_LOOPBACK_HTTP=false`. Invalid explicitly enabled settings
fail with a named configuration error; disabled settings require no provider
configuration and perform no discovery. HTTP is accepted only with the explicit
development flag and loopback host. Discovery endpoints and verification URI must
stay on the issuer origin; redirects are not followed. TLS verification stays on.

See [the development provider](../infrastructure/identity/README.md) for Keycloak,
independent provider/website databases, website environment and exact redirect
registration. The example hostname `auth.kyrion.ch` is not provisioned by source.

## API and persistence

Core uses typed HTTP JSON under `/v1/auth/central`: `GET config`, authenticated
`GET status`, `POST start` (`LOGIN` or `LINK`), `POST poll`, `POST complete`
(`confirm:true`), `POST cancel`, authenticated `DELETE link`. LINK start and unlink
require the current password with bounded reauthentication attempts. Web holds
the operation credential in a path-scoped HttpOnly cookie and requires CSRF and
same-origin mutation checks, including anonymous device-login requests. Neither
device codes nor opaque Core sessions are returned to browser JavaScript.

V46 adds `central_identity_link` and `central_auth_session` only. Unique keys and
a transaction advisory lock serialize mapping/login/removal; audit and mutation
share the transaction. Committed master's historical migrations are untouched:
V42 is Gateway, V43 joint Calendar, V44 personal disclosure and V45 household
delivery. The earlier
isolated Identity V44 is retained as a historical test fixture outside active
Flyway locations. An installation with that divergent history fails validation
and needs a separately reviewed compatibility plan. See
[ADR0040](adr/0042-central-identity-canonical-migration-integration.md). No checksum
repair or out-of-order bypass is provided.

## Installer and operational interfaces

The installer is unchanged. A later installer may expose the optional Core
settings above, preserve local bootstrap/invitation requirements, and offer
local-only versus connect-after-local-setup. It must never provision shared
client secrets on customer hosts, infer OWNER from central identity, overwrite
the local database, require cloud availability at startup, or create LAN callback
registrations. Preserve database plus original credential/audit/recovery keys.

External acceptance requires provider hosting/updates/backups, HTTPS and DNS,
controlled registration/email delivery, client policy and ingress abuse limits.
Development credentials are operator supplied and ignored; tests are not evidence
of production DNS, mail, TLS or release acceptance. See the
[handover](agent-handoffs/unified-identity-handover.md) for actual test evidence.

## Code linking user experience

The first local Profile section and its first navigation item are Link account.
The avatar shortcut targets `/profile#account-link`. A prominent code, Copy and
Open website actions replace the buried security-card workflow. Official
`auth.kyrion.ch/realms/kyrion/device` operations open the official website's
localized code-entry tab; other/isolated providers retain their own verification
page. Codes are entered in a same-origin, CSRF-protected website form and passed
only to the configured provider. The website stores no installation membership.

After local password-confirmed Link and provider approval, the local UI calls
Core's existing one-use `complete(confirm:true)` automatically. The current
local session, operation secret, expiry and signed identity remain required;
Core remains authoritative. This removes only the redundant final LINK click,
as recorded in [ADR 0052](adr/0052-visible-code-account-linking.md). LOGIN and
unlink confirmation remain unchanged. There are no new webhooks or inbound
callbacks to local installations.
