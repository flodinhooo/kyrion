export type Room = { id: string; name: string; createdAt: string; updatedAt: string };
export function isRoom(value: unknown): value is Room { if (!value || typeof value !== "object") return false; const room = value as Partial<Room>; return typeof room.id === "string" && typeof room.name === "string" && typeof room.createdAt === "string" && typeof room.updatedAt === "string"; }
export function isRoomList(value: unknown): value is Room[] { return Array.isArray(value) && value.every(isRoom); }
