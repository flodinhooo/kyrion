export type AccountConfig = {
  issuer: URL;
  origin: string;
  callback: string;
  clientId: string;
  clientSecret: string;
  databaseUrl: string;
  developmentHttp: boolean;
};

export function accountConfig(
  env: Record<string, string | undefined> = process.env,
): AccountConfig | null {
  if (
    env.KYRION_WEBSITE_ACCOUNT_ENABLED &&
    !["true", "false"].includes(env.KYRION_WEBSITE_ACCOUNT_ENABLED)
  )
    throw new Error("KYRION_WEBSITE_ACCOUNT_ENABLED must be true or false");
  if (env.KYRION_WEBSITE_ACCOUNT_ENABLED !== "true") return null;
  const required = (name: string) => {
    const value = env[name]?.trim();
    if (!value) throw new Error(`Missing account configuration: ${name}`);
    return value;
  };
  const developmentHttp =
    env.KYRION_WEBSITE_ACCOUNT_DEV_HTTP === "true" &&
    env.NODE_ENV !== "production";
  const validateUrl = (value: string) => {
    const url = new URL(value);
    if (
      url.username ||
      url.password ||
      url.hash ||
      url.search ||
      (url.protocol !== "https:" &&
        !(
          developmentHttp &&
          url.protocol === "http:" &&
          ["localhost", "127.0.0.1"].includes(url.hostname)
        ))
    ) {
      throw new Error(
        "Account URLs require HTTPS (loopback HTTP allowed only in explicit development mode)",
      );
    }
    return url;
  };
  const issuer = validateUrl(required("KYRION_WEBSITE_OIDC_ISSUER"));
  const originUrl = validateUrl(required("KYRION_WEBSITE_ORIGIN"));
  if (originUrl.pathname !== "/")
    throw new Error("Website origin must not contain a path");
  return {
    issuer,
    origin: originUrl.origin,
    callback: `${originUrl.origin}/api/account/callback`,
    clientId: required("KYRION_WEBSITE_OIDC_CLIENT_ID"),
    clientSecret: required("KYRION_WEBSITE_OIDC_CLIENT_SECRET"),
    databaseUrl: required("KYRION_WEBSITE_ACCOUNT_DATABASE_URL"),
    developmentHttp,
  };
}
