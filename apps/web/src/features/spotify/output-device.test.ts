import {expect, it} from "vitest";
import type {SpotifyDevice} from "./contracts";
import {resolveSpotifyOutput} from "./output-device";

const pi: SpotifyDevice = {
  id: "pi", name: "Kyrion Pi", type: "Speaker", active: false,
  restricted: false, volumePercent: 34, supportsVolume: true
};
const phone: SpotifyDevice = {...pi, id: "phone", name: "Phone"};

it("retains an accepted output selection when Spotify has no current playback", () => {
  expect(resolveSpotifyOutput([pi, phone], null, "pi")).toBe(pi);
});
it("follows actual playback or an active provider device ahead of an idle selection", () => {
  expect(resolveSpotifyOutput([pi, phone], "phone", "pi")).toBe(phone);
  const activePhone = {...phone, active: true};
  expect(resolveSpotifyOutput([pi, activePhone], null, "pi")).toBe(activePhone);
});
it("does not invent an output or retain a device absent from the current account list", () => {
  expect(resolveSpotifyOutput([pi, phone], null, null)).toBeUndefined();
  expect(resolveSpotifyOutput([phone], null, "pi")).toBeUndefined();
  expect(resolveSpotifyOutput([], "pi", "pi")).toBeUndefined();
});
