"use client";

import { Dialog } from "radix-ui";
import { useState } from "react";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import { isDeviceCommandResult, type RuntimeDevice } from "@/features/devices/contracts";

export function ZigbeeDeviceControlDialog({ device, open, onOpenChange }: {
  device: RuntimeDevice | null; open: boolean; onOpenChange: (open: boolean) => void;
}) {
  const { t } = useWorkspace(); const [brightness, setBrightness] = useState(74);
  const [color, setColor] = useState("#22d3ee");
  const [pending, setPending] = useState(false); const [failed, setFailed] = useState(false);
  if (!device) return null;
  async function command(capability: string, argumentsValue: object) {
    setPending(true); setFailed(false);
    const response = await fetch("/api/device-commands", { method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ capability, selector: { provider: "zigbee", deviceId: device!.id }, arguments: argumentsValue }) });
    const value: unknown = await response.json().catch(() => null);
    if (!response.ok || !isDeviceCommandResult(value) || value.succeeded !== 1) setFailed(true);
    setPending(false);
  }
  function applyColor() {
    const rgb = [1, 3, 5].map((index) => parseInt(color.slice(index, index + 2), 16) / 255);
    const max = Math.max(...rgb); const min = Math.min(...rgb); const delta = max - min; let hue = 0;
    if (delta) { if (max === rgb[0]) hue = 60 * (((rgb[1] - rgb[2]) / delta) % 6); else if (max === rgb[1]) hue = 60 * ((rgb[2] - rgb[0]) / delta + 2); else hue = 60 * ((rgb[0] - rgb[1]) / delta + 4); }
    void command("light.setColour", { hue: Math.round((hue + 360) % 360), saturation: Math.round(max === 0 ? 0 : delta / max * 100) });
  }
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="confirm-dialog-overlay" /><Dialog.Content className="device-dialog"><Dialog.Title>{device.displayName}</Dialog.Title><Dialog.Description>{t.homeDeviceControl} · Zigbee · kyrion-node</Dialog.Description>{failed && <p className="auth-error">{t.homeError}</p>}<div className="device-power"><button disabled={pending} onClick={() => void command("power.set", { on: true })}>{t.nanoleafTurnOn}</button><button disabled={pending} onClick={() => void command("power.set", { on: false })}>{t.nanoleafTurnOff}</button></div><div className="dialog-brightness"><label>{t.nanoleafBrightness}<strong>{brightness}%</strong><input type="range" min="1" max="100" value={brightness} onChange={(event) => setBrightness(Number(event.target.value))} /></label><button disabled={pending} onClick={() => void command("light.setBrightness", { brightness })}>{t.nanoleafApplyBrightness}</button></div><div className="color-controls"><label><span>{t.nanoleafColor}</span><input type="color" value={color} onChange={(event) => setColor(event.target.value)} /><button disabled={pending} onClick={applyColor}>{t.nanoleafApplyColor}</button></label></div><Dialog.Close asChild><button className="dialog-close">{t.homeClose}</button></Dialog.Close></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
