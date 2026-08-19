export const roomTypes = ["living_room", "office", "study", "bedroom", "children_room", "guest_room", "hobby_room", "gaming_room", "kitchen", "dining_room", "bathroom", "toilet", "hallway", "entrance", "storage", "basement", "laundry_room", "garage", "workshop", "balcony", "terrace", "garden", "other"] as const;
export type RoomType = typeof roomTypes[number];
export type Room = { id: string; name: string; roomType: RoomType; createdAt: string; updatedAt: string };
export function isRoom(value: unknown): value is Room { if (!value || typeof value !== "object") return false; const room = value as Partial<Room>; return typeof room.id === "string" && typeof room.name === "string" && roomTypes.includes(room.roomType as RoomType) && typeof room.createdAt === "string" && typeof room.updatedAt === "string"; }
export function isRoomList(value: unknown): value is Room[] { return Array.isArray(value) && value.every(isRoom); }
