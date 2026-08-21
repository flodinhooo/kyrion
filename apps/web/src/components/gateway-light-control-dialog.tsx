"use client";

import { useState } from "react";
import { Dialog } from "radix-ui";
import { useWorkspace } from "@/components/app-shell";
import { csrfHeader } from "@/features/auth/csrf";
import {
  isAsyncDeviceCommand, isDeviceCommandStatus, type RuntimeDevice,
} from "@/features/devices/contracts";
import { hsvToHex } from "@/features/devices/color";

export function GatewayLightControlDialog({ device, open, onOpenChange, onCommandSucceeded }: {
  device: RuntimeDevice | null; open: boolean; onOpenChange: (open: boolean) => void;
  onCommandSucceeded?: () => void;
}) {
  if (!device) return null;
  return <Content key={device.id} device={device} open={open} onOpenChange={onOpenChange} onCommandSucceeded={onCommandSucceeded} />;
}

function Content({ device, open, onOpenChange, onCommandSucceeded }: {
  device: RuntimeDevice; open: boolean; onOpenChange: (open: boolean) => void;
  onCommandSucceeded?: () => void;
}) {
  const { t } = useWorkspace();
  const [brightness, setBrightness] = useState(device.state?.brightness ?? 50);
  const [color, setColor] = useState(() => hsvToHex(
    device.state?.hue ?? null, device.state?.saturation ?? null,
  ));
  const [status, setStatus] = useState<"idle" | "pending" | "succeeded" | "failed">("idle");
  const pending = status === "pending";

  async function command(capability: string, argumentsValue: object) {
    setStatus("pending");
    const response = await fetch("/api/device-commands/async", {
      method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({
        capability, selector: { provider: device.provider, deviceId: device.id },
        arguments: argumentsValue,
      }),
    });
    const value: unknown = await response.json().catch(() => null);
    if (!response.ok || !isAsyncDeviceCommand(value)) { setStatus("failed"); return; }
    for (let attempt = 0; attempt < 80; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 100));
      const statusResponse = await fetch(`/api/device-commands/${value.commandId}`, { cache: "no-store" });
      const statusValue: unknown = await statusResponse.json().catch(() => null);
      if (!statusResponse.ok || !isDeviceCommandStatus(statusValue)) { setStatus("failed"); return; }
      if (statusValue.status === "succeeded") {
        setStatus("succeeded");
        window.setTimeout(() => onCommandSucceeded?.(), 5_500);
        return;
      }
      if (statusValue.status === "failed") { setStatus("failed"); return; }
    }
    setStatus("failed");
  }

  function applyColor() {
    const rgb = [1, 3, 5].map((index) => parseInt(color.slice(index, index + 2), 16) / 255);
    const max = Math.max(...rgb); const min = Math.min(...rgb); const delta = max - min; let hue = 0;
    if (delta) {
      if (max === rgb[0]) hue = 60 * (((rgb[1] - rgb[2]) / delta) % 6);
      else if (max === rgb[1]) hue = 60 * ((rgb[2] - rgb[0]) / delta + 2);
      else hue = 60 * ((rgb[0] - rgb[1]) / delta + 4);
    }
    void command("light.setColour", {
      hue: Math.round((hue + 360) % 360), saturation: Math.round(max === 0 ? 0 : delta / max * 100),
    });
  }

  const transport = device.provider === "bluetooth" ? "Bluetooth" : "Zigbee";
  return <Dialog.Root open={open} onOpenChange={onOpenChange}><Dialog.Portal>
    <Dialog.Overlay className="confirm-dialog-overlay" />
    <Dialog.Content className="device-dialog">
      <Dialog.Title>{device.displayName}</Dialog.Title>
      <Dialog.Description>{t.homeDeviceControl} · {transport} · kyrion-node</Dialog.Description>
      {status !== "idle" && <p className={status === "failed" ? "auth-error" : "command-status"} aria-live="polite">
        {status === "pending" ? t.commandPending : status === "succeeded" ? t.commandSucceeded : t.commandFailed}
      </p>}
      <div className="device-power">
        <button disabled={pending} onClick={() => void command("power.set", { on: true })}>{t.nanoleafTurnOn}</button>
        <button disabled={pending} onClick={() => void command("power.set", { on: false })}>{t.nanoleafTurnOff}</button>
      </div>
      <div className="dialog-brightness"><label>{t.nanoleafBrightness}<strong>{brightness}%</strong>
        <input type="range" min="1" max="100" value={brightness} onChange={(event) => setBrightness(Number(event.target.value))} />
      </label><button disabled={pending} onClick={() => void command("light.setBrightness", { brightness })}>{t.nanoleafApplyBrightness}</button></div>
      <div className="color-controls"><label><span>{t.nanoleafColor}</span>
        <input type="color" value={color} onChange={(event) => setColor(event.target.value)} />
        <button disabled={pending} onClick={applyColor}>{t.nanoleafApplyColor}</button>
      </label></div>
      <Dialog.Close asChild><button className="dialog-close">{t.homeClose}</button></Dialog.Close>
    </Dialog.Content>
  </Dialog.Portal></Dialog.Root>;
}
