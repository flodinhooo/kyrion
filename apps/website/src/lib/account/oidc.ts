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

export async function authorizationUrl(config: AccountConfig, flow: Flow) {
  const client = await discover(config);
  return oidc.buildAuthorizationUrl(client, {
    redirect_uri: config.callback,
    response_type: "code",
    scope: "openid",
    code_challenge: await oidc.calculatePKCECodeChallenge(flow.verifier),
    code_challenge_method: "S256",
    state: flow.state,
    nonce: flow.nonce,
    prompt: "login",
    max_age: "0",
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
    maxAge: 0,
  });
  const claims = result.claims();
  if (
    !claims ||
    typeof claims.sub !== "string" ||
    !claims.sub ||
    typeof claims.exp !== "number"
  )
    throw new Error("Invalid identity claims");
  // Tokens are deliberately discarded. They never authorize local Core APIs.
  return { issuer: claims.iss, subject: claims.sub, expiresAt: claims.exp };
}
