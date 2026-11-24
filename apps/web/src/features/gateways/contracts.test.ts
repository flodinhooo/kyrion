import { describe, expect, it } from "vitest";
import { isGatewayNodeList } from "./contracts";

describe("gateway contracts", () => {
  it("accepts bounded typed node health", () => {
    expect(isGatewayNodeList([{
      id: "node", displayName: "kyrion-node", hostname: "kyrion-node", availability: "online",
      agentVersion: "0.1.0", osName: "Debian", osVersion: "13", architecture: "aarch64",
      lastSeenAt: "2026-08-06T13:00:00Z", createdAt: "2026-08-06T12:00:00Z",
      health: {
        temperatureCelsius: 42.2, throttled: false, memoryTotalBytes: 8, memoryAvailableBytes: 7,
        storageTotalBytes: 64, storageAvailableBytes: 48,
        ethernet: { present: true, connected: true }, wifi: { present: true, connected: false },
        ipv6: true, bluetooth: true, systemState: "running",
        adapters: [{ id: "sonoff", protocol: "zigbee", vendor: "Itead", model: "Sonoff", serial: "serial", path: "/dev/serial/by-id/sonoff" }],
        audio: { capture: { id: "mic", displayName: "Microphone", transport: "usb" }, playback: { id: "speaker", displayName: "Pebble V3", transport: "bluetooth" } },
        zigbee: { permitJoin: false, channel: 15, devices: [] },
        bluetoothDevices: [],
        services: [{ id: "zigbee", status: "not_configured" }],
      },
    }])).toBe(true);
  });

  it("rejects unknown service status", () => {
    expect(isGatewayNodeList([{ services: [{ id: "zigbee", status: "root" }] }])).toBe(false);
  });

  it("accepts explicit unknown observations but refuses missing or invented booleans", () => {
    const health = {
      temperatureCelsius: null, throttled: null, memoryTotalBytes: 8, memoryAvailableBytes: 7,
      storageTotalBytes: 64, storageAvailableBytes: 48,
      ethernet: { present: null, connected: null }, wifi: { present: null, connected: null },
      ipv6: null, bluetooth: null, systemState: "unknown", adapters: [], audio: null,
      zigbee: null, bluetoothDevices: [], services: [],
    };
    const node = {
      id: "node", displayName: "fixture", hostname: "fixture", availability: "online",
      agentVersion: "0.2.0", osName: "Windows", osVersion: "fixture", architecture: "amd64",
      lastSeenAt: null, createdAt: "fixture", health,
    };
    expect(isGatewayNodeList([node])).toBe(true);
    expect(isGatewayNodeList([{ ...node, health: { ...health, throttled: undefined } }])).toBe(false);
    expect(isGatewayNodeList([{ ...node, health: { ...health, ipv6: "unknown" } }])).toBe(false);
  });
});
