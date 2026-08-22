"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Check, Cpu, LampDesk, Pencil, Plus, RadioTower, ScanLine, Trash2 } from "lucide-react";
import { Dialog } from "radix-ui";
import { useWorkspace } from "@/components/app-shell";
import { DeviceControlDialog } from "@/components/device-control-dialog";
import { GatewayLightControlDialog } from "@/components/gateway-light-control-dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { csrfHeader } from "@/features/auth/csrf";
import { isAsyncDeviceCommand, isButtonBindingList, isDeviceCommandResult, isDeviceCommandStatus, isRuntimeDeviceList, type ButtonAction, type ButtonBinding, type ButtonGesture, type DeviceClass, type RuntimeDevice } from "@/features/devices/contracts";
import { hsvToHex } from "@/features/devices/color";
import { isRoomList, roomTypes, type Room, type RoomType } from "@/features/home/contracts";
import {
  type IntegrationConnection,
  isConnectionList, isNanoleafState, type NanoleafState,
} from "@/features/integrations/contracts";

export default function DevicesPage() {
  const { t, locale } = useWorkspace();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [devices, setDevices] = useState<RuntimeDevice[]>([]);
  const [nanoleafStates, setNanoleafStates] = useState<Record<string, NanoleafState>>({});
  const [selected, setSelected] = useState<RuntimeDevice | null>(null);
  const [roomEditor, setRoomEditor] = useState<{
    mode: "create" | "edit";
    room: Room | null;
    name: string;
    roomType: RoomType;
  } | null>(null);
  const [deviceNames, setDeviceNames] = useState<Record<string, string>>({});
  const [deviceClasses, setDeviceClasses] = useState<Record<string, DeviceClass>>({});
  const [deleteRoom, setDeleteRoom] = useState<Room | null>(null);
  const [removeDevice, setRemoveDevice] = useState<RuntimeDevice | null>(null);
  const [commandStates, setCommandStates] = useState<Record<string, "pending" | "succeeded" | "failed">>({});
  const [roomCommandStates, setRoomCommandStates] = useState<Record<string, boolean>>({});
  const [buttonBindings, setButtonBindings] = useState<Record<string, ButtonBinding[]>>({});
  const [savingBindings, setSavingBindings] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [pending, setPending] = useState(false);

  const load = useCallback(async () => {
    const [roomResponse, connectionResponse, deviceResponse] = await Promise.all([
      fetch("/api/home/rooms", { cache: "no-store" }),
      fetch("/api/integrations/nanoleaf/connections", { cache: "no-store" }),
      fetch("/api/devices", { cache: "no-store" }),
    ]);
    const roomValue: unknown = await roomResponse.json();
    const connectionValue: unknown = await connectionResponse.json();
    const deviceValue: unknown = await deviceResponse.json();
    if (!roomResponse.ok || !connectionResponse.ok || !deviceResponse.ok
      || !isRoomList(roomValue) || !isConnectionList(connectionValue)
      || !isRuntimeDeviceList(deviceValue)) throw new Error();
    setRooms(roomValue);
    setConnections(connectionValue);
    setDevices(deviceValue);
  }, []);

  useEffect(() => {
    let disposed = false;
    const timeout = window.setTimeout(() => {
      void load().catch(() => { if (!disposed) setError(true); });
    }, 0);
    return () => { disposed = true; window.clearTimeout(timeout); };
  }, [load]);

  const refreshNanoleafStates = useCallback(async () => {
    const entries = await Promise.all(connections.slice(0, 20).map(async (connection) => {
      try {
        const response = await fetch(`/api/integrations/nanoleaf/connections/${connection.id}/state`, { cache: "no-store" });
        const value: unknown = await response.json();
        return response.ok && isNanoleafState(value) ? [connection.id, value] as const : null;
      } catch { return null; }
    }));
    setNanoleafStates(Object.fromEntries(entries.filter((entry): entry is readonly [string, NanoleafState] => entry !== null)));
  }, [connections]);

  useEffect(() => {
    if (connections.length === 0) return;
    const timeout = window.setTimeout(() => void refreshNanoleafStates(), 0);
    const interval = window.setInterval(() => void refreshNanoleafStates(), 10_000);
    return () => { window.clearTimeout(timeout); window.clearInterval(interval); };
  }, [connections.length, refreshNanoleafStates]);

  useEffect(() => {
    const buttons = devices.filter((device) => device.capabilities.some((capability) => capability.id === "button.events"));
    if (buttons.length === 0) return;
    let disposed = false;
    void Promise.all(buttons.map(async (button) => {
      const response = await fetch(`/api/devices/${button.id}/button-bindings`, { cache: "no-store" });
      const value: unknown = await response.json().catch(() => null);
      return response.ok && isButtonBindingList(value) ? [button.id, value] as const : null;
    })).then((entries) => {
      if (!disposed) setButtonBindings((current) => ({ ...current, ...Object.fromEntries(entries.filter((entry) => entry !== null)) }));
    });
    return () => { disposed = true; };
  }, [devices]);

  function updateButtonBinding(buttonId: string, gesture: ButtonGesture, targetValue: string, action?: ButtonAction) {
    setButtonBindings((current) => {
      const existing = current[buttonId] ?? [];
      const previous = existing.find((binding) => binding.gesture === gesture);
      const next = existing.filter((binding) => binding.gesture !== gesture);
      if (targetValue) next.push({
        gesture,
        targetDeviceId: targetValue.startsWith("device:") ? targetValue.slice(7) : null,
        targetRoomId: targetValue.startsWith("room:") ? targetValue.slice(5) : null,
        action: action ?? previous?.action ?? "toggle",
      });
      return { ...current, [buttonId]: next };
    });
  }

  async function saveButtonBindings(buttonId: string) {
    setSavingBindings(buttonId); setError(false);
    const response = await fetch(`/api/devices/${buttonId}/button-bindings`, {
      method: "PUT", headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({ bindings: buttonBindings[buttonId] ?? [] }),
    });
    const value: unknown = await response.json().catch(() => null);
    if (response.ok && isButtonBindingList(value)) setButtonBindings((current) => ({ ...current, [buttonId]: value }));
    else setError(true);
    setSavingBindings(null);
  }

  async function refreshObservations() {
    setPending(true);
    setError(false);
    try {
      const response = await fetch("/api/devices/observations/refresh", {
        method: "POST",
        headers: csrfHeader(),
      });
      const value: unknown = await response.json();
      if (!response.ok || !isRuntimeDeviceList(value)) throw new Error();
      setDevices(value);
    } catch {
      setError(true);
    } finally {
      setPending(false);
    }
  }

  async function createRoom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!roomEditor) return;
    const name = roomEditor.name.trim();
    if (!name) return;
    setPending(true);
    setError(false);
    const response = await fetch(roomEditor.mode === "create" ? "/api/home/rooms" : `/api/home/rooms/${roomEditor.room?.id}`, {
      method: roomEditor.mode === "create" ? "POST" : "PATCH",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({ name, roomType: roomEditor.roomType }),
    });
    if (response.ok) {
      setRoomEditor(null);
      await load();
    } else setError(true);
    setPending(false);
  }

  async function removeRoom() {
    if (!deleteRoom) return;
    setPending(true);
    const response = await fetch(`/api/home/rooms/${deleteRoom.id}`, {
      method: "DELETE",
      headers: csrfHeader(),
    });
    if (response.ok) { setDeleteRoom(null); setRoomEditor(null); await load(); } else setError(true);
    setPending(false);
  }

  async function assign(connectionId: string, roomId: string | null) {
    setPending(true);
    const response = await fetch(`/api/home/connections/${connectionId}/room`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({ roomId }),
    });
    if (response.ok) await load(); else setError(true);
    setPending(false);
  }

  async function renameDevice(device: RuntimeDevice) {
    const name = deviceNames[device.id]?.trim();
    if (!name) return;
    setPending(true); setError(false);
    const response = await fetch(`/api/home/connections/${device.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({ name, deviceClass: deviceClasses[device.id] ?? device.deviceClass }),
    });
    if (response.ok) {
      setDeviceNames((current) => { const next = { ...current }; delete next[device.id]; return next; });
      setDeviceClasses((current) => { const next = { ...current }; delete next[device.id]; return next; });
      await load();
    } else setError(true);
    setPending(false);
  }

  async function removeZigbeeDevice() {
    if (!removeDevice) return;
    setPending(true); setError(false);
    const response = await fetch(`/api/home/connections/${removeDevice.id}`, { method: "DELETE", headers: csrfHeader() });
    if (response.ok) { setRemoveDevice(null); setSelected(null); await load(); } else setError(true);
    setPending(false);
  }

  async function quickPower(id: string, on: boolean) {
    const device = devices.find((item) => item.id === id);
    if (device?.provider === "zigbee" || device?.provider === "bluetooth") {
      setCommandStates((current) => ({ ...current, [id]: "pending" }));
      const response = await fetch("/api/device-commands/async", {
        method: "POST", headers: { "Content-Type": "application/json", ...csrfHeader() },
        body: JSON.stringify({ capability: "power.set", selector: { provider: device.provider, deviceId: id }, arguments: { on } }),
      });
      const value: unknown = await response.json().catch(() => null);
      if (!response.ok || !isAsyncDeviceCommand(value)) { setCommandStates((current) => ({ ...current, [id]: "failed" })); return; }
      for (let attempt = 0; attempt < 80; attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 100));
        const statusResponse = await fetch(`/api/device-commands/${value.commandId}`, { cache: "no-store" });
        const statusValue: unknown = await statusResponse.json().catch(() => null);
        if (!statusResponse.ok || !isDeviceCommandStatus(statusValue) || statusValue.status === "failed") { setCommandStates((current) => ({ ...current, [id]: "failed" })); return; }
        if (statusValue.status === "succeeded") {
          setCommandStates((current) => ({ ...current, [id]: "succeeded" }));
          setDevices((current) => current.map((item) => item.id === id ? { ...item, state: item.state ? { ...item.state, on } : null } : item));
          return;
        }
      }
      setCommandStates((current) => ({ ...current, [id]: "failed" }));
      return;
    }
    setPending(true);
    const response = await fetch("/api/device-commands", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({
        capability: "power.set",
        selector: { provider: devices.find((device) => device.id === id)?.provider ?? "", deviceId: id },
        arguments: { on },
      }),
    });
    const value: unknown = await response.json().catch(() => null);
    if (response.ok && isDeviceCommandResult(value) && value.succeeded === 1) {
      setDevices((current) => current.map((device) => device.id === id
        ? { ...device, availability: "online", observedAt: new Date().toISOString(), state: device.state ? { ...device.state, on } : null }
        : device));
      setNanoleafStates((current) => current[id] ? { ...current, [id]: { ...current[id], on } } : current);
    } else {
      const availability = value && typeof value === "object"
        && (value as { code?: unknown }).code === "NANOLEAF_UNAVAILABLE" ? "offline" : "degraded";
      setDevices((current) => current.map((device) => device.id === id
        ? { ...device, availability, observedAt: new Date().toISOString() }
        : device));
    }
    setPending(false);
  }

  const groups = [
    ...rooms.map((room) => ({
      id: room.id,
      name: room.name,
      room,
      items: devices.filter((item) => item.room?.id === room.id),
    })),
    {
      id: "unassigned",
      name: t.homeUnassigned,
      room: null,
      items: devices.filter((item) => !item.room),
    },
  ];

  function availabilityText(device: RuntimeDevice | undefined) {
    if (!device || device.availability === "unknown") return t.homeUnknown;
    if (device.availability === "offline") return t.homeOffline;
    if (device.availability === "degraded") return t.homeDegraded;
    return t.homeOnline;
  }

  async function roomPower(roomId: string, items: RuntimeDevice[], on: boolean) {
    if (roomCommandStates[roomId]) return;
    setRoomCommandStates((current) => ({ ...current, [roomId]: true }));
    setCommandStates((current) => {
      const next = { ...current };
      for (const device of items) delete next[device.id];
      return next;
    });
    try {
      for (const device of items) await quickPower(device.id, on);
    } finally {
      setRoomCommandStates((current) => ({ ...current, [roomId]: false }));
      window.setTimeout(() => setCommandStates((current) => {
        const next = { ...current };
        for (const device of items) if (next[device.id] === "succeeded") delete next[device.id];
        return next;
      }), 2_500);
    }
  }

  return <section className="home-dashboard">
    <header>
      <div><p className="eyebrow">Kyrion Home</p><h1>{t.devicesTitle}</h1><p>{t.devicesDescription}</p></div>
      <div className="home-actions">
        <Link className="home-add-device" href="/devices/add"><span>+</span>{t.addDevice}</Link>
        <button type="button" disabled={pending} onClick={() => void refreshObservations()}>
          {pending ? t.homeRefreshingStatus : t.homeRefreshStatus}
        </button>
        <button type="button" disabled={pending} onClick={() => setRoomEditor({ mode: "create", room: null, name: "", roomType: "other" })}>
          <Plus aria-hidden="true" />{t.homeCreateRoom}
        </button>
      </div>
    </header>
    {error && <p className="auth-error">{t.homeError}</p>}
    <div className="room-grid">{groups.map((group) => <section className="room-card" key={group.id}>
      <div className="room-heading">
        <h2>{group.name}</h2>
        <div className="room-heading-actions">
          {group.items.some((device) => device.capabilities.some((capability) => capability.id === "power.set")) && (() => {
            const controllableItems = group.items.filter((device) => device.capabilities.some((capability) => capability.id === "power.set"));
            const roomIsOn = controllableItems.some((device) => device.state?.on === true || nanoleafStates[device.id]?.on === true);
            return <label className="room-power-switch"><span>{roomCommandStates[group.id] ? t.commandPending : roomIsOn ? t.zigbeeOn : t.zigbeeOff}</span><button type="button" role="switch" aria-checked={roomIsOn} aria-label={`${group.name}: ${roomIsOn ? t.devicesRoomOff : t.devicesRoomOn}`} disabled={pending || roomCommandStates[group.id]} onClick={() => void roomPower(group.id, controllableItems, !roomIsOn)}><i /></button></label>;
          })()}
          {group.room && <button className="room-edit-button" title={t.homeEditRoom} aria-label={`${t.homeEditRoom}: ${group.name}`} onClick={() => setRoomEditor({ mode: "edit", room: group.room, name: group.room.name, roomType: group.room.roomType })}>
          <Pencil aria-hidden="true" />
        </button>}</div>
      </div>
      {group.items.length === 0 ? <p className="room-empty">{t.homeNoDevices}</p> : <div className="room-devices">
        {group.items.map((device) => {
          const availability = device.availability;
          const nanoleafState = nanoleafStates[device.id];
          const liveState = nanoleafState ? {
            on: nanoleafState.on,
            brightness: nanoleafState.brightness,
            hue: nanoleafState.hue,
            saturation: nanoleafState.saturation,
            colorTemperature: nanoleafState.colorTemperature,
            occupancy: null,
            battery: null,
            illuminance: null,
            action: null,
            illumination: null,
          } : device.state;
          const hardwareName = nanoleafState?.name || device.hardwareName;
          const controllable = device.deviceClass === "light" && device.capabilities.some((capability) => capability.id === "power.set");
          const buttonDevice = device.capabilities.some((capability) => capability.id === "button.events");
          const powerTargets = devices.filter((candidate) => candidate.id !== device.id && candidate.capabilities.some((capability) => capability.id === "power.set"));
          const DeviceIcon = device.deviceClass === "light" ? LampDesk : device.deviceClass === "sensor" ? ScanLine : device.deviceClass === "switch" ? RadioTower : Cpu;
          return <article className={`device-card device-card-${device.deviceClass}${controllable ? " is-controllable" : ""}`} key={device.id} onClick={() => { if (controllable) setSelected(device); }}>
            <div>
              <div className="device-card-title"><span><DeviceIcon aria-hidden="true" /></span><strong>{device.displayName}</strong></div>
              <small>{hardwareName}</small>
              <small>{device.provider === "zigbee" ? "Zigbee · kyrion-node" : device.provider === "bluetooth" ? "Bluetooth · kyrion-node" : "Lokales Netzwerk · Nanoleaf"}</small>
              <span className={`device-status ${availability}`}>{availabilityText(device)}</span>
              {device?.observedAt && <small>{t.homeObservedAt}: {new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "medium" }).format(new Date(device.observedAt))}</small>}
            </div>
            {controllable && <button>{t.homeOpenControls}</button>}
            {liveState && controllable && <div className="device-live-state" aria-label={t.homeCurrentState}>
              <span className={`state-pill ${liveState.on ? "is-on" : "is-off"}`}>{liveState.on === null ? t.homeUnknown : liveState.on ? t.zigbeeOn : t.zigbeeOff}</span>
              <span>{t.homeCurrentBrightness}: <strong>{liveState.brightness ?? "–"}%</strong></span>
              <span>{t.homeCurrentColor}: <i className="color-swatch" style={{ backgroundColor: hsvToHex(liveState.hue, liveState.saturation) }} /></span>
            </div>}
            {liveState && !controllable && <div className="device-live-state sensor-live-state" aria-label={t.homeCurrentState}>
              {liveState.occupancy !== null && <span>{t.sensorMotion}: <strong>{liveState.occupancy ? t.sensorDetected : t.sensorClear}</strong></span>}
              {liveState.illuminance !== null && <span>{t.sensorIlluminance}: <strong>{liveState.illuminance} lx</strong></span>}
              {liveState.illumination !== null && <span>{t.sensorIlluminance}: <strong>{liveState.illumination === "dim" ? t.sensorDim : t.sensorBright}</strong></span>}
              {liveState.battery !== null && <span>{t.sensorBattery}: <strong>{liveState.battery}%</strong></span>}
              {liveState.action && <span>{t.sensorLastAction}: <strong>{liveState.action}</strong></span>}
            </div>}
            {buttonDevice && <div className="button-bindings" onClick={(event) => event.stopPropagation()}>
              <div><strong>{t.buttonBindingsTitle}</strong><small>{t.buttonBindingsDescription}</small></div>
              {(["single", "double", "long"] as const).map((gesture) => {
                const binding = (buttonBindings[device.id] ?? []).find((item) => item.gesture === gesture);
                return <div className="button-binding-row" key={gesture}>
                  <span>{gesture === "single" ? t.buttonGestureSingle : gesture === "double" ? t.buttonGestureDouble : t.buttonGestureLong}</span>
                  <select aria-label={`${gesture}: ${t.buttonTarget}`} value={binding?.targetDeviceId ? `device:${binding.targetDeviceId}` : binding?.targetRoomId ? `room:${binding.targetRoomId}` : ""} onChange={(event) => updateButtonBinding(device.id, gesture, event.target.value)}>
                    <option value="">{t.buttonNotAssigned}</option>
                    <optgroup label={t.buttonTargetRooms}>{rooms.filter((room) => devices.some((candidate) => candidate.room?.id === room.id && candidate.capabilities.some((capability) => capability.id === "power.set"))).map((room) => <option value={`room:${room.id}`} key={room.id}>{room.name}</option>)}</optgroup>
                    <optgroup label={t.buttonTargetDevices}>{powerTargets.map((target) => <option value={`device:${target.id}`} key={target.id}>{target.displayName}</option>)}</optgroup>
                  </select>
                  <select aria-label={`${gesture}: ${t.buttonAction}`} disabled={!binding} value={binding?.action ?? "toggle"} onChange={(event) => updateButtonBinding(device.id, gesture, binding?.targetDeviceId ? `device:${binding.targetDeviceId}` : binding?.targetRoomId ? `room:${binding.targetRoomId}` : "", event.target.value as ButtonAction)}>
                    <option value="toggle">{t.buttonActionToggle}</option><option value="turn_on">{t.buttonActionOn}</option><option value="turn_off">{t.buttonActionOff}</option>
                  </select>
                </div>;
              })}
              <button type="button" disabled={savingBindings === device.id} onClick={() => void saveButtonBindings(device.id)}>{savingBindings === device.id ? t.buttonSaving : t.buttonSave}</button>
            </div>}
            {controllable && <div className="quick-controls" onClick={(event) => event.stopPropagation()}>
              <button disabled={pending || commandStates[device.id] === "pending"} onClick={() => void quickPower(device.id, true)}>{t.nanoleafTurnOn}</button>
              <button disabled={pending || commandStates[device.id] === "pending"} onClick={() => void quickPower(device.id, false)}>{t.nanoleafTurnOff}</button>
            </div>}
            {commandStates[device.id] && <small className={commandStates[device.id] === "failed" ? "auth-error" : "command-status"} aria-live="polite">{commandStates[device.id] === "pending" ? t.commandPending : commandStates[device.id] === "succeeded" ? t.commandSucceeded : t.commandFailed}</small>}
            <div className="device-rename" onClick={(event) => event.stopPropagation()}>
              <input aria-label={t.homeRenameDevice} maxLength={160} value={deviceNames[device.id] ?? device.displayName} onChange={(event) => setDeviceNames((current) => ({ ...current, [device.id]: event.target.value }))} />
              <select aria-label={t.deviceClass} value={deviceClasses[device.id] ?? device.deviceClass} onChange={(event) => setDeviceClasses((current) => ({ ...current, [device.id]: event.target.value as DeviceClass }))}>{(["light", "switch", "sensor", "other"] as const).map((value) => <option key={value} value={value}>{t.deviceClasses[value]}</option>)}</select>
              <button disabled={pending || (deviceNames[device.id] === undefined && deviceClasses[device.id] === undefined)} onClick={() => void renameDevice(device)}>{t.homeRenameDevice}</button>
            </div>
            {device.provider === "zigbee" && <button className="danger" disabled={pending} onClick={(event) => { event.stopPropagation(); setRemoveDevice(device); }}>{t.homeRemoveDevice}</button>}
            <label onClick={(event) => event.stopPropagation()}>{t.homeAssignRoom}
              <select value={device.room?.id ?? ""} disabled={pending} onChange={(event) => void assign(device.id, event.target.value || null)}>
                <option value="">{t.homeUnassigned}</option>
                {rooms.map((room) => <option value={room.id} key={room.id}>{room.name}</option>)}
              </select>
            </label>
          </article>;
        })}
      </div>}
    </section>)}</div>
    <DeviceControlDialog connection={selected?.provider === "nanoleaf" ? connections.find((item) => item.id === selected.id) ?? null : null} open={selected?.provider === "nanoleaf"} onOpenChange={(open) => { if (!open) setSelected(null); }} />
    <GatewayLightControlDialog device={(selected?.provider === "zigbee" || selected?.provider === "bluetooth") && selected.capabilities.some((capability) => capability.id === "power.set") ? selected : null} open={!!selected && (selected.provider === "zigbee" || selected.provider === "bluetooth") && selected.capabilities.some((capability) => capability.id === "power.set")} onOpenChange={(open) => { if (!open) setSelected(null); }} onCommandSucceeded={load} />
    <Dialog.Root open={roomEditor !== null} onOpenChange={(open) => { if (!open && !pending && !deleteRoom) setRoomEditor(null); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="confirm-dialog-overlay" />
        <Dialog.Content className="confirm-dialog-content room-dialog">
          <Dialog.Title>{roomEditor?.mode === "create" ? t.homeCreateRoom : t.homeEditRoom}</Dialog.Title>
          <Dialog.Description>{roomEditor?.mode === "create" ? t.homeCreateRoomDescription : t.homeEditRoomDescription}</Dialog.Description>
          {roomEditor && <form onSubmit={createRoom}>
            <label>{t.homeRoomName}
              <input autoFocus maxLength={120} required value={roomEditor.name} onChange={(event) => setRoomEditor((current) => current ? { ...current, name: event.target.value } : current)} />
            </label>
            <label>{t.homeRoomType}
              <select value={roomEditor.roomType} onChange={(event) => setRoomEditor((current) => current ? { ...current, roomType: event.target.value as RoomType } : current)}>
                {roomTypes.map((type) => <option value={type} key={type}>{t.homeRoomTypes[type]}</option>)}
              </select>
            </label>
            <div className="room-dialog-actions">
              {roomEditor.mode === "edit" && <button type="button" className="danger" disabled={pending} onClick={() => setDeleteRoom(roomEditor.room)}>
                <Trash2 aria-hidden="true" />{t.homeDeleteRoom}
              </button>}
              <button type="submit" disabled={pending || !roomEditor.name.trim()}>
                <Check aria-hidden="true" />{roomEditor.mode === "create" ? t.homeCreateRoom : t.homeSaveRoom}
              </button>
            </div>
          </form>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
    <ConfirmDialog open={deleteRoom !== null} onOpenChange={(open) => { if (!open) setDeleteRoom(null); }} title={t.homeDeleteRoom} description={t.homeDeleteRoomDescription} confirmLabel={t.homeDeleteRoom} cancelLabel={t.cancel} pending={pending} onConfirm={() => void removeRoom()} />
    <ConfirmDialog open={removeDevice !== null} onOpenChange={(open) => { if (!open) setRemoveDevice(null); }} title={t.homeRemoveDevice} description={t.homeRemoveDeviceDescription} confirmLabel={t.homeRemoveDevice} cancelLabel={t.cancel} pending={pending} onConfirm={() => void removeZigbeeDevice()} />
  </section>;
}
