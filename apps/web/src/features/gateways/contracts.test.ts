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
        services: [{ id: "zigbee", status: "not_configured" }],
      },
    }])).toBe(true);
  });

  it("rejects unknown service status", () => {
    expect(isGatewayNodeList([{ services: [{ id: "zigbee", status: "root" }] }])).toBe(false);
  });
});
