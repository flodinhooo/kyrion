import { describe, expect, it } from "vitest";
import { MAX_ROOM_FAVORITES, parseRoomFavorites, toggleRoomFavorite } from "./favorites";

describe("room favorite preferences", () => {
  it("recovers from absent, malformed and untrusted browser storage", () => {
    for (const value of [null, "{", "{}", "null", "x".repeat(5000)]) expect(parseRoomFavorites(value)).toEqual([]);
    expect(parseRoomFavorites('["room-1",1,null,"room-1","../other","room-2"]')).toEqual(["room-1", "room-2"]);
  });
  it("bounds favorites and preserves the selected order", () => {
    const ids = Array.from({ length: 12 }, (_, index) => `room-${index}`);
    expect(parseRoomFavorites(JSON.stringify(ids))).toEqual(ids.slice(0, MAX_ROOM_FAVORITES));
    const full = ids.slice(0, MAX_ROOM_FAVORITES);
    expect(toggleRoomFavorite(full, "new-room")).toEqual(full);
    expect(toggleRoomFavorite(full, "room-0")).toEqual(full.slice(1));
    expect(toggleRoomFavorite(["room-2"], "room-1")).toEqual(["room-2", "room-1"]);
  });
});
