"use client";

import { DragEvent, FormEvent, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Box, House, LampDesk, Plus } from "lucide-react";
import { Dialog } from "radix-ui";
import { useWorkspace } from "@/components/app-shell";
import { SnapshotStatus } from "@/components/snapshot-status";
import { HomeRoomFavorites } from "@/components/home-room-favorites";
import { DeviceControlDialog } from "@/components/device-control-dialog";
import { GatewayLightControlDialog } from "@/components/gateway-light-control-dialog";
import { csrfHeader } from "@/features/auth/csrf";
import { isRuntimeDeviceList, type RuntimeDevice } from "@/features/devices/contracts";
import { isRoomList, roomTypes, type Room, type RoomType } from "@/features/home/contracts";
import { isConnectionList, type IntegrationConnection } from "@/features/integrations/contracts";

const roomSymbols: Partial<Record<RoomType, string>> = {
  living_room: "◫", office: "⌨", study: "⌨", bedroom: "◇", children_room: "☆",
  kitchen: "♨", dining_room: "♢", bathroom: "◉", hallway: "↔", entrance: "⌂",
  garage: "▣", workshop: "⚒", balcony: "☀", terrace: "☀", garden: "♧",
};

export default function HomePage() {
  const { t } = useWorkspace();
  const [rooms, setRooms] = useState<Room[]>([]);
  const [devices, setDevices] = useState<RuntimeDevice[]>([]);
  const [connections, setConnections] = useState<IntegrationConnection[]>([]);
  const [selectedRoomId, setSelectedRoomId] = useState<string | null>(null);
  const [selectedDevice, setSelectedDevice] = useState<RuntimeDevice | null>(null);
  const [roomEditor, setRoomEditor] = useState<{ name: string; roomType: RoomType } | null>(null);
  const [draggedDeviceId, setDraggedDeviceId] = useState<string | null>(null);
  const [dropRoomId, setDropRoomId] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    const [roomsResponse, devicesResponse, connectionsResponse] = await Promise.all([
      fetch("/api/home/rooms", { cache: "no-store" }),
      fetch("/api/devices", { cache: "no-store" }),
      fetch("/api/integrations/nanoleaf/connections", { cache: "no-store" }),
    ]);
    const roomValue: unknown = await roomsResponse.json();
    const deviceValue: unknown = await devicesResponse.json();
    const connectionValue: unknown = await connectionsResponse.json();
    if (!roomsResponse.ok || !devicesResponse.ok || !connectionsResponse.ok || !isRoomList(roomValue) || !isRuntimeDeviceList(deviceValue) || !isConnectionList(connectionValue)) throw new Error();
    setRooms(roomValue);
    setDevices(deviceValue);
    setConnections(connectionValue);
    setLoaded(true);
    setUpdatedAt(new Date());
    setError(false);
  }, []);

  useEffect(() => {
    let disposed = false;
    const timeout = window.setTimeout(() => void load().catch(() => { if (!disposed) setError(true); }), 0);
    return () => { disposed = true; window.clearTimeout(timeout); };
  }, [load]);

  async function refresh() {
    if (refreshing) return;
    setRefreshing(true);
    try { await load(); } catch { setError(true); }
    finally { setRefreshing(false); }
  }

  async function assignDevice(deviceId: string, roomId: string) {
    const previous = devices;
    const room = rooms.find((item) => item.id === roomId);
    if (!room) return;
    setDevices((current) => current.map((device) => device.id === deviceId ? { ...device, room: { id: room.id, name: room.name, roomType: room.roomType } } : device));
    const response = await fetch(`/api/home/connections/${deviceId}/room`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({ roomId }),
    });
    if (!response.ok) { setDevices(previous); setError(true); }
    setDraggedDeviceId(null);
    setDropRoomId(null);
  }

  function drop(event: DragEvent<HTMLElement>, roomId: string) {
    event.preventDefault();
    const deviceId = event.dataTransfer.getData("text/kyrion-device") || draggedDeviceId;
    if (deviceId) void assignDevice(deviceId, roomId);
  }

  async function createRoom(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!roomEditor?.name.trim()) return;
    const response = await fetch("/api/home/rooms", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeader() },
      body: JSON.stringify({ name: roomEditor.name.trim(), roomType: roomEditor.roomType }),
    });
    if (!response.ok) { setError(true); return; }
    setRoomEditor(null);
    await load();
  }

  function openDevice(device: RuntimeDevice) {
    setSelectedRoomId(null);
    setSelectedDevice(device);
  }

  const selectedRoom = rooms.find((room) => room.id === selectedRoomId) ?? null;
  const selectedDevices = selectedRoom ? devices.filter((device) => device.room?.id === selectedRoom.id) : [];
  const unassigned = devices.filter((device) => !device.room);
  const attention = devices.filter((device) => device.availability !== "online");

  return <section className="home-dashboard spatial-home">
    <header>
      <div><h1>{t.homeTitle}</h1><p>{t.homeDescription}</p></div>
      <div className="home-actions"><button type="button" onClick={() => setRoomEditor({ name: "", roomType: "other" })}><Plus aria-hidden="true" />{t.homeCreateRoom}</button><Link href="/devices"><Box aria-hidden="true" />{t.homeOpenDeviceControls}</Link><Link className="home-add-device" href="/devices/add"><Plus aria-hidden="true" />{t.addDevice}</Link></div>
    </header>
    <SnapshotStatus error={error} loaded={loaded} busy={refreshing} updatedAt={updatedAt} onReload={() => void refresh()} />
    {loaded && <div className="home-summary" aria-label={t.homeTitle}>
      <a href="#home-rooms"><span>{t.homeSummaryRooms}</span><strong>{rooms.length}</strong><House aria-hidden="true" /></a>
      <Link href="/devices"><span>{t.homeSummaryDevices}</span><strong>{devices.length}</strong><Box aria-hidden="true" /></Link>
      <Link href="/devices"><span>{t.homeSummaryOnline}</span><strong>{devices.filter((device) => device.availability === "online").length}<small> / {devices.length}</small></strong><LampDesk aria-hidden="true" /></Link>
    </div>}
    {loaded && <HomeRoomFavorites rooms={rooms} onOpen={setSelectedRoomId} />}
    {loaded && !error && devices.length > 0 && <section className="home-attention" aria-labelledby="home-attention-title">
      <div className="home-section-heading"><div><h2 id="home-attention-title">{t.homeAttention}</h2><p>{attention.length ? t.homeAttentionHint : t.homeAttentionEmpty}</p></div><Link href="/devices">{t.homeAttentionOpen}<ArrowRight aria-hidden="true" /></Link></div>
      {attention.length > 0 && <ul>{attention.map((device) => <li key={device.id}><span><strong>{device.displayName}</strong><small>{device.room?.name ?? t.homeUnassigned}</small></span><span className={`device-status ${device.availability}`}>{device.availability === "offline" ? t.homeOffline : device.availability === "degraded" ? t.homeDegraded : t.homeUnknown}</span></li>)}</ul>}
    </section>}
    {loaded && rooms.length === 0 && <div className="home-empty">
      <h2>{t.homeEmptyTitle}</h2><p>{t.homeEmptyDescription}</p>
      <button type="button" onClick={() => setRoomEditor({ name: "", roomType: "other" })}><Plus aria-hidden="true" />{t.homeCreateRoom}</button>
    </div>}
    {rooms.length > 0 && <p className="floor-plan-hint">{t.homeFloorPlanHint}</p>}
    <div id="home-rooms" className={`home-plan${rooms.length === 0 ? " is-empty" : ""}`} aria-label={t.homeTitle}>
      {rooms.map((room, index) => {
        const items = devices.filter((device) => device.room?.id === room.id);
        const isSelected = selectedRoomId === room.id;
        return <button className={`plan-room plan-room-${index % 6} ${isSelected ? "selected" : ""} ${dropRoomId === room.id ? "drop-target" : ""}`} key={room.id}
          onClick={() => setSelectedRoomId(room.id)} onDragOver={(event) => { event.preventDefault(); setDropRoomId(room.id); }} onDragLeave={() => setDropRoomId(null)} onDrop={(event) => drop(event, room.id)}>
          <span className="room-symbol" aria-hidden="true">{roomSymbols[room.roomType] ?? "□"}</span>
          <strong>{room.name}</strong><small>{t.homeDevicesCount.replace("{count}", String(items.length))}</small>
          <span className="plan-device-dots">{items.slice(0, 5).map((device) => <i className={device.state?.on ? "on" : ""} key={device.id} />)}</span>
          {dropRoomId === room.id && <em>{t.homeDropDevice}</em>}
        </button>;
      })}
    </div>
    {unassigned.length > 0 && <section className="unassigned-tray"><div><h2>{t.homeUnassigned}</h2><p>{t.homeDropDevice}</p></div><div>{unassigned.map((device) => <button draggable key={device.id} onDragStart={(event) => { setDraggedDeviceId(device.id); event.dataTransfer.setData("text/kyrion-device", device.id); event.dataTransfer.effectAllowed = "move"; }} onDragEnd={() => { setDraggedDeviceId(null); setDropRoomId(null); }}><LampDesk aria-hidden="true" />{device.displayName}</button>)}</div></section>}
    <Dialog.Root open={selectedRoom !== null} onOpenChange={(open) => { if (!open) setSelectedRoomId(null); }}><Dialog.Portal><Dialog.Overlay className="confirm-dialog-overlay" /><Dialog.Content className="device-dialog room-overview-dialog">
      <Dialog.Title>{selectedRoom?.name}</Dialog.Title><Dialog.Description>{t.homeDevicesCount.replace("{count}", String(selectedDevices.length))}</Dialog.Description>
      <div className="room-dialog-device-list">{selectedDevices.length === 0 ? <p>{t.homeNoDevices}</p> : selectedDevices.map((device) => <button type="button" onClick={() => openDevice(device)} key={device.id}><LampDesk aria-hidden="true" /><span><strong>{device.displayName}</strong><small>{device.hardwareName}</small><small className={`device-status ${device.availability}`}>{device.availability === "online" ? t.homeOnline : device.availability === "offline" ? t.homeOffline : device.availability === "degraded" ? t.homeDegraded : t.homeUnknown}</small></span><span>{t.homeOpenControls}<ArrowRight aria-hidden="true" /></span></button>)}</div>
      <Dialog.Close asChild><button className="dialog-close">{t.homeClose}</button></Dialog.Close>
    </Dialog.Content></Dialog.Portal></Dialog.Root>
    <Dialog.Root open={roomEditor !== null} onOpenChange={(open) => { if (!open) setRoomEditor(null); }}><Dialog.Portal><Dialog.Overlay className="confirm-dialog-overlay" /><Dialog.Content className="confirm-dialog-content room-dialog">
      <Dialog.Title>{t.homeCreateRoom}</Dialog.Title><Dialog.Description>{t.homeCreateRoomDescription}</Dialog.Description>
      {roomEditor && <form onSubmit={createRoom}><label>{t.homeRoomName}<input autoFocus required maxLength={120} value={roomEditor.name} onChange={(event) => setRoomEditor((current) => current ? { ...current, name: event.target.value } : current)} /></label><label>{t.homeRoomType}<select value={roomEditor.roomType} onChange={(event) => setRoomEditor((current) => current ? { ...current, roomType: event.target.value as RoomType } : current)}>{roomTypes.map((type) => <option value={type} key={type}>{t.homeRoomTypes[type]}</option>)}</select></label><div className="room-dialog-actions"><button type="submit" disabled={!roomEditor.name.trim()}><Plus aria-hidden="true" />{t.homeCreateRoom}</button></div></form>}
    </Dialog.Content></Dialog.Portal></Dialog.Root>
    <DeviceControlDialog connection={selectedDevice?.provider === "nanoleaf" ? connections.find((item) => item.id === selectedDevice.id) ?? null : null} open={selectedDevice?.provider === "nanoleaf"} onOpenChange={(open) => { if (!open) setSelectedDevice(null); }} />
    <GatewayLightControlDialog device={selectedDevice?.provider === "zigbee" || selectedDevice?.provider === "bluetooth" ? selectedDevice : null} open={selectedDevice?.provider === "zigbee" || selectedDevice?.provider === "bluetooth"} onOpenChange={(open) => { if (!open) setSelectedDevice(null); }} onCommandSucceeded={load} />
  </section>;
}
