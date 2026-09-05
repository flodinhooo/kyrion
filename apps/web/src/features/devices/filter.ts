import type { DeviceAvailability, DeviceClass, RuntimeDevice } from "./contracts";

export type DeviceFilters = {
  query: string;
  availability: DeviceAvailability | "all";
  deviceClass: DeviceClass | "all";
};

export function hasDeviceFilters(filters: DeviceFilters): boolean {
  return filters.query.trim().length > 0 || filters.availability !== "all" || filters.deviceClass !== "all";
}

function normalize(value: string): string {
  return value.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "").replace(/ß/g, "ss");
}

export function filterDevices(devices: RuntimeDevice[], filters: DeviceFilters): RuntimeDevice[] {
  const words = normalize(filters.query).trim().split(/\s+/).filter(Boolean);
  return devices.filter((device) => {
    if (filters.availability !== "all" && device.availability !== filters.availability) return false;
    if (filters.deviceClass !== "all" && device.deviceClass !== filters.deviceClass) return false;
    const text = normalize([device.displayName, device.hardwareName, device.room?.name ?? ""].join(" "));
    return words.every((word) => text.includes(word));
  });
}
