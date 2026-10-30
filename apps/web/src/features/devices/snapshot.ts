import type { RuntimeDevice } from "./contracts";

/** Keep newer confirmed observations when a slower request finishes last. */
export function mergeDeviceSnapshots(previous: RuntimeDevice[], incoming: RuntimeDevice[]): RuntimeDevice[] {
  const existing = new Map(previous.map(device => [device.id, device]));
  return incoming.map(device => {
    const before = existing.get(device.id);
    if (!before?.observedAt || !device.observedAt || Date.parse(device.observedAt) >= Date.parse(before.observedAt)) return device;
    return { ...device, state: before.state, availability: before.availability,
      observedAt: before.observedAt, diagnosticReason: before.diagnosticReason };
  });
}
