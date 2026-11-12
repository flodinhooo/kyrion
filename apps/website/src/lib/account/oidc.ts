import * as oidc from "openid-client";
import type { AccountConfig } from "./config";
import type { Flow } from "./store";

export async function discover(config: AccountConfig) {
  const client = await oidc.discovery(
    config.issuer,
    config.clientId,
    {
      client_secret: config.clientSecret,
      id_token_signed_response_alg: "RS256",
    },
    oidc.ClientSecretBasic(config.clientSecret),
    {
      timeout: 10,
      execute: config.developmentHttp
        ? [oidc.allowInsecureRequests, oidc.enableNonRepudiationChecks]
        : [oidc.enableNonRepudiationChecks],
    },
  );
  return client;
}

export async function authorizationUrl(
  config: AccountConfig,
  flow: Flow,
  register = false,
) {
  const client = await discover(config);
  return oidc.buildAuthorizationUrl(client, {
    redirect_uri: config.callback,
    response_type: "code",
    scope: "openid email",
    code_challenge: await oidc.calculatePKCECodeChallenge(flow.verifier),
    code_challenge_method: "S256",
    state: flow.state,
    nonce: flow.nonce,
    ...(register ? { prompt: "create" } : {}),
    ui_locales: flow.locale,
  });
}

export async function authenticate(
  config: AccountConfig,
  callback: URL,
  flow: Flow,
) {
  const client = await discover(config);
  const result = await oidc.authorizationCodeGrant(client, callback, {
    pkceCodeVerifier: flow.verifier,
    expectedState: flow.state,
    expectedNonce: flow.nonce,
    idTokenExpected: true,
  });
  const claims = result.claims();
  if (
    !claims ||
    typeof claims.sub !== "string" ||
    !claims.sub ||
    typeof claims.exp !== "number" ||
    claims.email_verified !== true ||
    !result.refresh_token
  )
    throw new Error("Invalid identity claims");
  return {
    issuer: claims.iss,
    subject: claims.sub,
    expiresAt: claims.exp,
    refreshToken: result.refresh_token,
  };
}

export class IdentityRevoked extends Error {}

export async function renewIdentity(
  config: AccountConfig,
  refreshToken: string,
) {
  try {
    const client = await discover(config);
    const result = await oidc.refreshTokenGrant(client, refreshToken);
    const claims = result.claims();
    if (
      !claims ||
      !claims.sub ||
      typeof claims.exp !== "number" ||
      claims.email_verified !== true
    )
      throw new IdentityRevoked("Identity unavailable");
    return {
      issuer: claims.iss,
      subject: claims.sub,
      expiresAt: claims.exp,
      refreshToken: result.refresh_token ?? refreshToken,
    };
  } catch (error) {
    if (
      error instanceof oidc.ResponseBodyError &&
      error.error === "invalid_grant"
    )
      throw new IdentityRevoked("Identity revoked");
    throw error;
  }
}

export async function revokeRefresh(
  config: AccountConfig,
  refreshToken: string,
) {
  await oidc.tokenRevocation(await discover(config), refreshToken, {
    token_type_hint: "refresh_token",
  });
}
