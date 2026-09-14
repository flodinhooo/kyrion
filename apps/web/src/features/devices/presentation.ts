import type { RuntimeDevice } from "./contracts";

export type DevicePresentation = {
  primaryLabel: string;
  primaryValue: string;
  primaryTone: "positive" | "neutral" | "warning";
  secondaryMetrics: Array<{ label: string; value: string }>;
  hasPrimaryValue: boolean;
};

type PresentationText = {
  closed: string; open: string; motionDetected: string; noMotion: string;
  on: string; off: string; unknown: string; temperature: string; humidity: string;
  battery: string; brightness: string; color: string; lastAction: string;
};

export function deriveDevicePresentation(device: RuntimeDevice, state: RuntimeDevice["state"], text: PresentationText): DevicePresentation {
  const capabilities = new Set(device.capabilities.map((capability) => capability.id));
  const metrics: Array<{ label: string; value: string }> = [];
  const add = (label: string, value: number | string | null | undefined, suffix = "") => {
    if (value !== null && value !== undefined) metrics.push({ label, value: `${value}${suffix}` });
  };

  if (capabilities.has("contact.read")) {
    const open = state?.on === true;
    return { primaryLabel: "", primaryValue: state?.on == null ? text.unknown : open ? text.open : text.closed, primaryTone: open ? "warning" : "positive", secondaryMetrics: batteryMetric(state, text), hasPrimaryValue: state?.on != null };
  }
  if (capabilities.has("occupancy.read")) {
    return { primaryLabel: "", primaryValue: state?.occupancy == null ? text.unknown : state.occupancy ? text.motionDetected : text.noMotion, primaryTone: state?.occupancy ? "warning" : "neutral", secondaryMetrics: batteryMetric(state, text), hasPrimaryValue: state?.occupancy != null };
  }
  if (capabilities.has("temperature.read") && state?.temperatureCelsius != null) {
    add(text.humidity, state.relativeHumidity, "%");
    add(text.battery, state.battery, "%");
    return { primaryLabel: text.temperature, primaryValue: `${state.temperatureCelsius} °C`, primaryTone: "neutral", secondaryMetrics: metrics, hasPrimaryValue: true };
  }
  if (capabilities.has("humidity.read") && state?.relativeHumidity != null) {
    add(text.temperature, state.temperatureCelsius, " °C");
    add(text.battery, state.battery, "%");
    return { primaryLabel: text.humidity, primaryValue: `${state.relativeHumidity}%`, primaryTone: "neutral", secondaryMetrics: metrics, hasPrimaryValue: true };
  }
  if (capabilities.has("button.events")) {
    add(text.lastAction, state?.action, "");
    return { primaryLabel: text.lastAction, primaryValue: state?.action ?? text.unknown, primaryTone: "neutral", secondaryMetrics: batteryMetric(state, text), hasPrimaryValue: state?.action != null };
  }
  if (capabilities.has("power.set") && state?.on != null) {
    add(text.brightness, state.brightness, "%");
    return { primaryLabel: "", primaryValue: state.on ? text.on : text.off, primaryTone: state.on ? "positive" : "neutral", secondaryMetrics: metrics, hasPrimaryValue: true };
  }
  add(text.battery, state?.battery, "%");
  add(text.temperature, state?.temperatureCelsius, " °C");
  add(text.humidity, state?.relativeHumidity, "%");
  return { primaryLabel: "", primaryValue: text.unknown, primaryTone: "neutral", secondaryMetrics: metrics, hasPrimaryValue: false };
}

function batteryMetric(state: RuntimeDevice["state"], text: PresentationText) {
  const metrics: Array<{ label: string; value: string }> = [];
  if (state?.battery != null) metrics.push({ label: text.battery, value: `${state.battery}%` });
  return metrics;
}
