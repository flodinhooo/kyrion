import { describe, expect, it } from "vitest";
import type { RuntimeDevice } from "./contracts";
import { filterDevices, hasDeviceFilters, type DeviceFilters } from "./filter";

const devices: RuntimeDevice[] = [
  { id: "light", displayName: "Große Leuchte", hardwareName: "Panel", provider: "nanoleaf", deviceClass: "light", availability: "online", room: { id: "room", name: "Büro", roomType: "office" }, capabilities: [], observedAt: null, state: null },
  { id: "sensor", displayName: "Bewegung", hardwareName: "Sensor", provider: "zigbee", deviceClass: "sensor", availability: "unknown", room: null, capabilities: [], observedAt: null, state: null },
];
const empty: DeviceFilters = { query: "", availability: "all", deviceClass: "all" };

describe("device overview filtering", () => {
  it("matches words across names and rooms without case or accent sensitivity", () => {
    expect(filterDevices(devices, { ...empty, query: "  BURO grosse PANEL " })).toEqual([devices[0]]);
  });
  it("combines search, availability and class instead of mixing their results", () => {
    expect(filterDevices(devices, { query: "panel", availability: "unknown", deviceClass: "light" })).toEqual([]);
    expect(filterDevices(devices, { query: "sensor", availability: "unknown", deviceClass: "sensor" })).toEqual([devices[1]]);
    expect(filterDevices(devices, { ...empty, availability: "offline" })).toEqual([]);
  });
  it("preserves the input, ordering, unassigned devices and empty-query behavior", () => {
    expect(filterDevices(devices, { ...empty, query: "  " })).toEqual(devices);
    expect(devices.map((device) => device.id)).toEqual(["light", "sensor"]);
    expect(hasDeviceFilters({ ...empty, query: "  " })).toBe(false);
    expect(hasDeviceFilters({ ...empty, deviceClass: "sensor" })).toBe(true);
    expect(hasDeviceFilters({ ...empty, availability: "unknown" })).toBe(true);
  });
});
