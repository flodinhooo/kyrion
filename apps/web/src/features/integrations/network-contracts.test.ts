import { describe, expect, it } from "vitest";
import { isNetworkDeviceList } from "./network-contracts";
import { isRuntimeDevice } from "../devices/contracts";

describe("local network discovery", () => {
  it("accepts discovered devices independently of available integrations", () => {
    const devices = [
      { provider: "nanoleaf", name: "Panels", host: "192.168.1.2", port: 16021 },
      { provider: "shelly", name: "shellyhtg3", host: "192.168.1.3", port: 80 },
    ];
    expect(isNetworkDeviceList(devices)).toBe(true);
    expect(isNetworkDeviceList([{ ...devices[0], connected: true }])).toBe(true);
    expect(isNetworkDeviceList([{ ...devices[0], connected: "true" }])).toBe(false);
    expect(isNetworkDeviceList([{ provider: "network", name: "Printer", host: "192.168.1.4", port: 631 }])).toBe(true);
    expect(isNetworkDeviceList([{ provider: "network", name: "192.168.1.5", host: "192.168.1.5", port: 0 }])).toBe(true);
    expect(isNetworkDeviceList([{ ...devices[1], port: 65536 }])).toBe(false);
    expect(isNetworkDeviceList([{ ...devices[1], provider: "unknown" }])).toBe(false);
    expect(isNetworkDeviceList([{ ...devices[1], host: "https://example.com" }])).toBe(false);
    expect(isNetworkDeviceList(new Array(513).fill(devices[0]))).toBe(false);
  });

  it("accepts timestamped sensor readings and rejects invalid values", () => {
    const state = { on: null, brightness: null, hue: null, saturation: null, colorTemperature: null,
      occupancy: null, battery: 90, illuminance: null, action: null, illumination: null,
      temperatureCelsius: 0, relativeHumidity: 48, measuredAt: "2026-09-05T12:00:00Z" };
    const device = { id: "sensor", provider: "shelly", deviceClass: "sensor", displayName: "Bedroom",
      hardwareName: "Shelly", room: null, capabilities: [{ id: "temperature.read" }],
      availability: "unknown", observedAt: null, state };
    expect(isRuntimeDevice(device)).toBe(true);
    for (const invalid of [{ temperatureCelsius: NaN }, { relativeHumidity: 101 },
      { temperatureCelsius: "20" }, { measuredAt: "invalid" }]) {
      expect(isRuntimeDevice({ ...device, state: { ...state, ...invalid } })).toBe(false);
    }
  });
});
