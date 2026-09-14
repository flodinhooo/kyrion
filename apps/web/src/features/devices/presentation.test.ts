import { describe, expect, it } from "vitest";
import { deriveDevicePresentation } from "./presentation";
import type { RuntimeDevice } from "./contracts";

const text = { closed: "Geschlossen", open: "Offen", motionDetected: "Bewegung erkannt", noMotion: "Keine Bewegung", on: "An", off: "Aus", unknown: "Unbekannt", temperature: "Temperatur", humidity: "Luftfeuchtigkeit", battery: "Batterie", brightness: "Helligkeit", color: "Farbe", lastAction: "Letzte Aktion" };
const device = (capabilities: string[]): RuntimeDevice => ({ id: "1", provider: "test", deviceClass: "sensor", displayName: "Sensor", hardwareName: "Test", room: null, capabilities: capabilities.map((id) => ({ id })), availability: "online", observedAt: null, state: null });

describe("device presentation", () => {
  it("renders open and closed contact states from the real on value", () => {
    expect(deriveDevicePresentation(device(["contact.read"]), { on: true, brightness: null, hue: null, saturation: null, colorTemperature: null, occupancy: null, battery: 80, illuminance: null, action: null, illumination: null }, text).primaryValue).toBe("Offen");
    expect(deriveDevicePresentation(device(["contact.read"]), { on: false, brightness: null, hue: null, saturation: null, colorTemperature: null, occupancy: null, battery: 80, illuminance: null, action: null, illumination: null }, text).primaryValue).toBe("Geschlossen");
  });
  it("prioritizes current motion and environmental values", () => {
    expect(deriveDevicePresentation(device(["occupancy.read"]), { on: null, brightness: null, hue: null, saturation: null, colorTemperature: null, occupancy: true, battery: 50, illuminance: null, action: null, illumination: null }, text).primaryValue).toBe("Bewegung erkannt");
    expect(deriveDevicePresentation(device(["temperature.read", "humidity.read"]), { on: null, brightness: null, hue: null, saturation: null, colorTemperature: null, occupancy: null, battery: null, illuminance: null, action: null, illumination: null, temperatureCelsius: 21.5, relativeHumidity: 45 }, text).primaryValue).toContain("21.5");
  });
  it("falls back to unknown without inventing state", () => {
    expect(deriveDevicePresentation(device([]), null, text).hasPrimaryValue).toBe(false);
  });
});
