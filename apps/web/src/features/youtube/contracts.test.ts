import { describe, expect, it } from "vitest";
import { isYouTubeEmbed, isYouTubeRequest } from "./contracts";

describe("YouTube boundary contracts", () => {
  it("bounds requests before passing provider-specific link validation to Core", () => {
    expect(isYouTubeRequest({ url: "https://youtu.be/M7lc1UVf-VE", source: "VIDEO" })).toBe(true);
    expect(isYouTubeRequest({ url: "https://music.youtube.com/watch?v=M7lc1UVf-VE", source: "MUSIC" })).toBe(true);
    expect(isYouTubeRequest({ url: " ", source: "VIDEO" })).toBe(false);
    expect(isYouTubeRequest({ url: "x".repeat(2049), source: "VIDEO" })).toBe(false);
    expect(isYouTubeRequest({ url: "https://youtu.be/M7lc1UVf-VE", source: "COMMAND" })).toBe(false);
  });
  it("rejects unsafe frame and link destinations", () => {
    const value = { embedUrl: "https://www.youtube-nocookie.com/embed/M7lc1UVf-VE?autoplay=0", watchUrl: "https://www.youtube.com/watch?v=M7lc1UVf-VE" };
    expect(isYouTubeEmbed(value)).toBe(true);
    expect(isYouTubeEmbed({ ...value, embedUrl: "https://evil.test/embed/M7lc1UVf-VE" })).toBe(false);
    expect(isYouTubeEmbed({ ...value, embedUrl: "https://user@www.youtube-nocookie.com/embed/M7lc1UVf-VE" })).toBe(false);
    expect(isYouTubeEmbed({ ...value, watchUrl: "javascript:alert(1)" })).toBe(false);
    expect(isYouTubeEmbed({ ...value, watchUrl: "https://www.youtube.com/redirect" })).toBe(false);
  });
});
