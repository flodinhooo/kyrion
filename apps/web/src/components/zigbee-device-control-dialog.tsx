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
  const [pending, setPending] = useState(false); const [failed, setFailed] = useState(false);
  if (!device) return null;
  async function command(capability: string, argumentsValue: object) {
    setPending(true); setFailed(false);
    const response = await fetch("/api/device-commands", { method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() }, body: JSON.stringify({ capability, selector: { provider: "zigbee", deviceId: device!.id }, arguments: argumentsValue }) });
    const value: unknown = await response.json().catch(() => null);
    if (!response.ok || !isDeviceCommandResult(value) || value.succeeded !== 1) setFailed(true);
    setPending(false);
  }
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal><Dialog.Overlay className="confirm-dialog-overlay" /><Dialog.Content className="device-dialog"><Dialog.Title>{device.displayName}</Dialog.Title><Dialog.Description>{t.homeDeviceControl} · Zigbee · kyrion-node</Dialog.Description>{failed && <p className="auth-error">{t.homeError}</p>}<div className="device-power"><button disabled={pending} onClick={() => void command("power.set", { on: true })}>{t.nanoleafTurnOn}</button><button disabled={pending} onClick={() => void command("power.set", { on: false })}>{t.nanoleafTurnOff}</button></div><div className="dialog-brightness"><label>{t.nanoleafBrightness}<strong>{brightness}%</strong><input type="range" min="1" max="100" value={brightness} onChange={(event) => setBrightness(Number(event.target.value))} /></label><button disabled={pending} onClick={() => void command("light.setBrightness", { brightness })}>{t.nanoleafApplyBrightness}</button></div><Dialog.Close asChild><button className="dialog-close">{t.homeClose}</button></Dialog.Close></Dialog.Content></Dialog.Portal></Dialog.Root>;
}
