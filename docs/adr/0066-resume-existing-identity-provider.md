# ADR 0066: Preserve the configured identity provider during installer resume

Status: Accepted

The regular installer already defaults to the repository's Kyrion account issuer
and public local Core client. It also supports explicit operator arguments. These
defaults must not replace or conflict with an existing installation's previously
approved provider when its original command arguments are no longer present.

Keep the current product defaults in the existing identity-settings owner. The
parser distinguishes omitted arguments from explicit overrides. For continuation,
load the verified installation under its existing lock and prefer the saved public
provider configuration. Validate it with `validate_identity`, including the
existing strict field contract. An explicitly conflicting issuer or client is
refused before configuration/runtime changes. Missing saved settings on a legacy
installation use the current reviewed defaults and existing Core linking flow.

Fresh setup continues to use the existing product default or an explicit reviewed
override. Both are displayed before installation approval. Customer passwords and
client secrets are never installer configuration. No additional release-channel
schema, configuration store, provider discovery service or account system is
needed for this behavior.

Browser/device authorization, accounts, membership, roles, offline access and
recovery remain in the existing Core architecture. Source/native terminal paths
share the same selection rule. Isolated configuration tests do not establish
productive provider or default-browser acceptance.
