import catalog from "@/content/releases.json";

export type PublishedInstaller = {
  version: string;
  platform: "windows-amd64" | "linux-amd64" | "linux-arm64";
  url: string;
  bytes: number;
  sha256: string;
  publishedAt: string;
  notesUrl: string;
};

// This public metadata is generated from an actually published GitHub release.
// It contains no installation state, host survey or local account information.
export function publishedInstallers(value: unknown): PublishedInstaller[] {
  if (
    typeof value !== "object" ||
    value === null ||
    !("schemaVersion" in value) ||
    value.schemaVersion !== 1 ||
    !("releases" in value) ||
    !Array.isArray(value.releases)
  ) {
    throw new Error("RELEASE_CATALOG_INVALID");
  }
  const seen = new Set<string>();
  return value.releases.map((item: unknown) => {
    if (
      typeof item !== "object" ||
      item === null ||
      !("version" in item) ||
      typeof item.version !== "string" ||
      !/^\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?$/.test(item.version) ||
      !("platform" in item) ||
      (item.platform !== "windows-amd64" &&
        item.platform !== "linux-amd64" &&
        item.platform !== "linux-arm64") ||
      !("url" in item) ||
      typeof item.url !== "string" ||
      !("notesUrl" in item) ||
      typeof item.notesUrl !== "string" ||
      !("bytes" in item) ||
      !Number.isSafeInteger(item.bytes) ||
      Number(item.bytes) <= 0 ||
      !("sha256" in item) ||
      typeof item.sha256 !== "string" ||
      !/^[a-f0-9]{64}$/.test(item.sha256) ||
      !("publishedAt" in item) ||
      typeof item.publishedAt !== "string" ||
      !Number.isFinite(Date.parse(item.publishedAt))
    ) {
      throw new Error("RELEASE_CATALOG_INVALID");
    }
    const base = `https://github.com/flodinhooo/kyrion/releases/`;
    if (
      !item.url.startsWith(`${base}download/v${item.version}/`) ||
      item.notesUrl !== `${base}tag/v${item.version}` ||
      !/^https:\/\/github\.com\/flodinhooo\/kyrion\/releases\/download\/[^/]+\/[A-Za-z0-9._-]+$/.test(
        item.url,
      ) ||
      (item.platform === "windows-amd64"
        ? !item.url.endsWith(".exe")
        : !item.url.endsWith(".tar.gz"))
    ) {
      throw new Error("RELEASE_CATALOG_INVALID");
    }
    const key = `${item.version}/${item.platform}`;
    if (seen.has(key)) throw new Error("RELEASE_CATALOG_INVALID");
    seen.add(key);
    return {
      version: item.version,
      platform: item.platform,
      url: item.url,
      bytes: Number(item.bytes),
      sha256: item.sha256,
      publishedAt: item.publishedAt,
      notesUrl: item.notesUrl,
    };
  });
}

export const installers = publishedInstallers(catalog);
