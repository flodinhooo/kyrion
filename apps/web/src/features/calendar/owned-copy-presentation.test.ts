import { beforeEach, describe, expect, it, vi } from "vitest";
import { ownedCopyLinks, confirmedOwnedCopies } from "./owned-copy-presentation";
import { normalizeHouseholdEvents } from "./calendar-model";
vi.mock("@/lib/server-auth", () => ({ CORE_SERVICE_URL: "http://core.test", csrfIsValid: vi.fn(), requireApiSession: vi.fn() }));
import { requireApiSession } from "@/lib/server-auth";
import { GET } from "@/app/api/calendar/events/route";
const id = "8d32bc75-bdf0-4f81-9bdb-b287cff71264";
const remoteId = "a".repeat(64);
const native = { id, title: "Dinner", description: "Family", startsAt: "2026-11-10T10:00:00.123456Z", endsAt: "2026-11-10T11:00:00Z",
  revision: 2, participantIds: ["partner"], createdBy: "partner", canEdit: true, canDelete: true };
const remote = { id: remoteId, summary: native.title, description: native.description, start: native.startsAt, end: native.endsAt,
  status: "confirmed", etag: "private-version", recurring: false, kyrionId: remoteId };
const link = { eventId: id, remoteId, etag: remote.etag, revision: 2 };
const household = () => normalizeHouseholdEvents([native])!;
describe("confirmed own calendar copies", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.mocked(requireApiSession).mockResolvedValue({ token: "server-only", user: { id: "member", username: "Member" } });
  });
  it("suppresses only a fully confirmed identical copy alongside a present native event", () => {
    expect([...confirmedOwnedCopies({ items: [remote] }, household(), [link])]).toEqual([`google:${remoteId}`]);
    expect(confirmedOwnedCopies({ items: [remote] }, null, [link]).size).toBe(0);
    expect(confirmedOwnedCopies({ items: [remote] }, [], [link]).size).toBe(0);
    expect(confirmedOwnedCopies({ items: [remote] }, household(), null).size).toBe(0);
  });
  it.each([
    { summary: "Private external change" }, { description: "External description" }, { etag: "new-version" },
    { kyrionId: "other" }, { recurring: true }, { status: "cancelled" }, { status: "unknown" },
    { start: "2026-11-10", end: "2026-11-11" }, { start: "2026-11-10T10:00:00.123457Z" },
    { end: "2026-11-10T11:01:00Z" }, { start: "bad" },
  ])("retains changed or unverifiable remote event %j", patch => {
    expect(confirmedOwnedCopies({ items: [{ ...remote, ...patch }] }, household(), [link]).size).toBe(0);
  });
  it("retains copies from different canonical revisions and unrelated equal-looking events", () => {
    expect(confirmedOwnedCopies({ items: [remote] }, household(), [{ ...link, revision: 1 }]).size).toBe(0);
    expect(confirmedOwnedCopies({ items: [{ ...remote, id: "different" }] }, household(), [link]).size).toBe(0);
  });
  it("compares equivalent offsets without losing sub-millisecond precision", () => {
    const copy = { ...remote, start: "2026-11-10T11:00:00.123456+01:00", end: "2026-11-10T12:00:00+01:00" };
    expect(confirmedOwnedCopies({ items: [copy] }, household(), [link]).size).toBe(1);
  });
  it("rejects malformed or unbounded link metadata as a whole", () => {
    expect(ownedCopyLinks([{ ...link, revision: "2" }])).toBeNull();
    expect(ownedCopyLinks([{ ...link, eventId: "" }])).toBeNull();
    expect(ownedCopyLinks([{ ...link, etag: "bad\nheader" }])).toBeNull();
    expect(ownedCopyLinks(Array.from({ length: 1001 }, () => link))).toBeNull();
  });
  it("keeps linkage and private marker metadata out of the combined browser response", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json([]))
      .mockResolvedValueOnce(Response.json({ items: [remote] })).mockResolvedValueOnce(Response.json([native]))
      .mockResolvedValueOnce(Response.json([link]));
    const response = await GET(new Request("http://web.test/api/calendar/events?calendarId=chosen&start=2026-11-01T00:00:00Z&end=2026-12-01T00:00:00Z"));
    const value = await response.json();
    expect(value.items).toHaveLength(1);
    expect(value.items[0].id).toBe(`household:${id}`);
    expect(value.copies.status).toBe("ready");
    expect(JSON.stringify(value.items)).not.toContain("private-version");
    expect(JSON.stringify(value.items)).not.toContain(remoteId);
    // The separate personal view retains the account's own editable Google copy.
    expect(value.personalItems).toEqual([expect.objectContaining({id: `google:${remoteId}`, etag: "private-version"})]);
    expect(JSON.stringify(value)).not.toContain('"kyrionId"');
    expect(JSON.stringify(value)).not.toContain('"eventId"');
    expect(upstream.mock.calls[3][0]).toBe("http://core.test/v1/calendar/household-copy-links?start=2026-11-01T00%3A00%3A00Z&end=2026-12-01T00%3A00%3A00Z&calendarId=chosen");
    expect(upstream.mock.calls[3][1]).toMatchObject({ headers: { Authorization: "Bearer server-only" }, cache: "no-store" });
  });
  it("retains both representations when the optional Core link endpoint fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json([]))
      .mockResolvedValueOnce(Response.json({ items: [remote] })).mockResolvedValueOnce(Response.json([native]))
      .mockResolvedValueOnce(Response.json({ code: "NOT_FOUND" }, { status: 404 }));
    const value = await (await GET(new Request("http://web.test/api/calendar/events?calendarId=chosen"))).json();
    expect(value.items).toHaveLength(2);
    expect(value.copies.status).toBe("unavailable");
  });
  it("never hides a provider event when household loading fails", async () => {
    const upstream = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(Response.json([]))
      .mockResolvedValueOnce(Response.json({ items: [remote] })).mockResolvedValueOnce(Response.json({ code: "UNAVAILABLE" }, { status: 503 }));
    const value = await (await GET()).json();
    expect(value.items).toHaveLength(1);
    expect(value.items[0].source).toBe("google");
    expect(upstream).toHaveBeenCalledTimes(3);
  });
});
