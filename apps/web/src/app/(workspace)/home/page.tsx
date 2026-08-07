"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useWorkspace } from "@/components/app-shell";
import { DeviceControlDialog } from "@/components/device-control-dialog";
import { ZigbeeDeviceControlDialog } from "@/components/zigbee-device-control-dialog";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { csrfHeader } from "@/features/auth/csrf";
import { isDeviceCommandResult, isRuntimeDeviceList, type RuntimeDevice } from "@/features/devices/contracts";
import { isRoomList, type Room } from "@/features/home/contracts";
import {
  type IntegrationConnection,
  isConnectionList,
} from "@/features/integrations/contracts";

export default function HomePage() {
  const { t, locale } = useWorkspace();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [devices, setDevices] = useState<RuntimeDevice[]>([]);
  const [selected, setSelected] = useState<RuntimeDevice | null>(null);
  const [editing, setEditing] = useState<Record<string, string>>({});
  const [deleteRoom, setDeleteRoom] = useState<Room | null>(null);
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
    const form = event.currentTarget;
    const name = String(new FormData(form).get("name") ?? "").trim();
    if (!name) return;
    setPending(true);
    const response = await fetch("/api/home/rooms", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({ name }),
    });
    if (response.ok) { form.reset(); await load(); } else setError(true);
    setPending(false);
  }

  async function rename(room: Room) {
    const name = editing[room.id]?.trim();
    if (!name) return;
    setPending(true);
    const response = await fetch(`/api/home/rooms/${room.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({ name }),
    });
    if (response.ok) {
      setEditing((current) => { const next = { ...current }; delete next[room.id]; return next; });
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
    if (response.ok) { setDeleteRoom(null); await load(); } else setError(true);
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

  async function quickPower(id: string, on: boolean) {
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
        ? { ...device, availability: "online", observedAt: new Date().toISOString() }
        : device));
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

  return <section className="home-dashboard">
    <header>
      <div><p className="eyebrow">Kyrion Home</p><h1>{t.homeTitle}</h1><p>{t.homeDescription}</p></div>
      <form onSubmit={createRoom}>
        <Link className="home-add-device" href="/devices/add"><span>+</span>{t.addDevice}</Link>
        <button type="button" disabled={pending} onClick={() => void refreshObservations()}>
          {pending ? t.homeRefreshingStatus : t.homeRefreshStatus}
        </button>
        <input name="name" maxLength={120} placeholder={t.homeRoomName} required />
        <button disabled={pending}>{t.homeCreateRoom}</button>
      </form>
    </header>
    {error && <p className="auth-error">{t.homeError}</p>}
    <div className="room-grid">{groups.map((group) => <section className="room-card" key={group.id}>
      <div className="room-heading">
        {group.room && editing[group.id] !== undefined
          ? <input autoFocus value={editing[group.id]} onChange={(event) => setEditing((current) => ({ ...current, [group.id]: event.target.value }))} />
          : <h2>{group.name}</h2>}
        <div>{group.room && <>
          <button onClick={() => editing[group.id] !== undefined ? void rename(group.room!) : setEditing((current) => ({ ...current, [group.id]: group.name }))}>
            {editing[group.id] !== undefined ? t.homeSaveRoom : t.homeRenameRoom}
          </button>
          <button className="danger" onClick={() => setDeleteRoom(group.room)}>{t.homeDeleteRoom}</button>
        </>}</div>
      </div>
      {group.items.length === 0 ? <p className="room-empty">{t.homeNoDevices}</p> : <div className="room-devices">
        {group.items.map((device) => {
          const availability = device.availability;
          return <article key={device.id} onClick={() => setSelected(device)}>
            <div>
              <strong>{device.displayName}</strong>
              <small>{device.provider === "zigbee" ? "Zigbee · kyrion-node" : "Nanoleaf"}</small>
              <span className={`device-status ${availability}`}>{availabilityText(device)}</span>
              {device?.observedAt && <small>{t.homeObservedAt}: {new Intl.DateTimeFormat(locale, { dateStyle: "short", timeStyle: "medium" }).format(new Date(device.observedAt))}</small>}
            </div>
            <button>{t.homeOpenControls}</button>
            <div className="quick-controls" onClick={(event) => event.stopPropagation()}>
              <button disabled={pending} onClick={() => void quickPower(device.id, true)}>{t.nanoleafTurnOn}</button>
              <button disabled={pending} onClick={() => void quickPower(device.id, false)}>{t.nanoleafTurnOff}</button>
            </div>
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
    <ZigbeeDeviceControlDialog device={selected?.provider === "zigbee" ? selected : null} open={selected?.provider === "zigbee"} onOpenChange={(open) => { if (!open) setSelected(null); }} />
    <ConfirmDialog open={deleteRoom !== null} onOpenChange={(open) => { if (!open) setDeleteRoom(null); }} title={t.homeDeleteRoom} description={t.homeDeleteRoomDescription} confirmLabel={t.homeDeleteRoom} cancelLabel={t.cancel} pending={pending} onConfirm={() => void removeRoom()} />
  </section>;
}
