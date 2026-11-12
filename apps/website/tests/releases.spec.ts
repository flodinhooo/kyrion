import { expect, test } from "@playwright/test";
import { publishedInstallers } from "../src/lib/releases";

const fixture = {
  version: "1.0.0",
  platform: "windows-amd64",
  url: "https://github.com/flodinhooo/kyrion/releases/download/v1.0.0/kyrion-installer-1.0.0-windows-amd64.exe",
  bytes: 8000000,
  sha256: "a".repeat(64),
  publishedAt: "2026-11-11T00:00:00Z",
  notesUrl: "https://github.com/flodinhooo/kyrion/releases/tag/v1.0.0",
};

test("published artifact catalog rejects untrusted URLs and malformed release metadata", () => {
  expect(publishedInstallers({ schemaVersion: 1, releases: [] })).toEqual([]);
  expect(
    publishedInstallers({ schemaVersion: 1, releases: [fixture] }),
  ).toEqual([fixture]);
  for (const item of [
    { ...fixture, url: "https://example.test/unpublished.exe" },
    { ...fixture, bytes: -1 },
    { ...fixture, sha256: "invalid" },
    { ...fixture, version: "latest" },
    { ...fixture, publishedAt: "invalid" },
  ]) {
    expect(() =>
      publishedInstallers({ schemaVersion: 1, releases: [item] }),
    ).toThrow("RELEASE_CATALOG_INVALID");
  }
  expect(() =>
    publishedInstallers({ schemaVersion: 1, releases: [fixture, fixture] }),
  ).toThrow("RELEASE_CATALOG_INVALID");
});
