import type {SpotifyDevice} from "./contracts";

export function resolveSpotifyOutput(
  devices: SpotifyDevice[],
  playbackDeviceId: string | null,
  confirmedSelectionId: string | null,
): SpotifyDevice | undefined {
  return devices.find((device) => device.id === playbackDeviceId)
    ?? devices.find((device) => device.active)
    ?? devices.find((device) => device.id === confirmedSelectionId);
}
