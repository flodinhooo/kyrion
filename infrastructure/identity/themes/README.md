# Kyrion identity theme

`kyrion` inherits `keycloak.v2`. Only CSS is overridden; upstream forms, labels,
password-manager attributes, validation, required-action handling and protocol
templates remain intact. No JavaScript, password proxy or administrator access
is added to the website. See [ADR 0068](../../../docs/adr/0068-customer-identity-experience.md).

The acceptance Compose stack mounts this directory and imports a realm selecting
`loginTheme: kyrion`. Existing realms are not changed by editing an import file.
For an existing provider, mount `./themes/kyrion` read-only at
`/opt/keycloak/themes/kyrion`, preserve the current realm configuration, then set
its login theme to `kyrion`. Keep production theme caching enabled. Preserve the
provider image/digest, database volume, secrets and other realm settings.

Verify login, registration, verification, recovery and device confirmation, light
and dark schemes, mobile overflow, visible focus and password-manager attributes.
Rollback selects the previous login theme; no schema or user migration is needed.
The normal website settings entry stays on the website and requests individual
profile/password actions. Authentication still visibly uses the trusted identity
origin. Advanced credential administration is a separate follow-up.
