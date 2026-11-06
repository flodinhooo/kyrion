import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import { describe, expect, it } from "vitest";

// Separate Node processes make timezone tests independent of the host/worker TZ.
// Existing TypeScript dev tooling compiles the real implementation, not a copy.
const model = ts.transpileModule(readFileSync(fileURLToPath(new URL("./calendar-model.ts", import.meta.url)), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
function probe(zone: string, instant: string, gap: string) {
  const input = { instant, gap };
  const script = `${model}\nconst fixture = ${JSON.stringify(input)};
    const event = { id:'household:fixture', source:'household', title:'Original', startsAt:fixture.instant, endsAt:'2026-11-02T12:00:45.123456Z', revision:2 };
    const editor = editorForEvent(event);
    let gapRejected = false;
    try { editorInstant({...editor, startsAt:fixture.gap, originalTime:undefined}, 'startsAt'); } catch(error) { gapRejected = error instanceof CalendarTimeError; }
    const unchanged = householdEventPayload({...editor,title:'Title changed'}, '${zone}');
    const changed = editorInstant({...editor, startsAt:'2026-11-02T08:30'}, 'startsAt');
    const crossStart = new Date(Date.parse(fixture.instant)-45*60*1000).toISOString();
    const crossEnd = new Date(Date.parse(fixture.instant)-15*60*1000).toISOString();
    const crossing = editorForEvent({...event,startsAt:crossStart,endsAt:crossEnd});
    const crossPayload = householdEventPayload(crossing,'${zone}');
    console.log(JSON.stringify({ input:editor.startsAt, original:unchanged.startsAt, end:unchanged.endsAt,
      oldRoundTrip:new Date(editor.startsAt).toISOString(), changed, gapRejected,
      crossInputReversed:crossing.endsAt<crossing.startsAt,
      crossDuration:Date.parse(crossPayload.endsAt)-Date.parse(crossPayload.startsAt) }));`;
  return JSON.parse(execFileSync(process.execPath, ["--input-type=module"], {
    input: script, encoding: "utf8", env: { ...process.env, TZ: zone }, timeout: 10_000,
  })) as { input: string; original: string; end: string; oldRoundTrip: string; changed: string; gapRejected: boolean; crossInputReversed: boolean; crossDuration: number };
}
describe("calendar absolute instants across clock changes", () => {
  it.each([
    ["Europe/Zurich", "2026-10-25T01:30:45.123456Z", "2026-03-29T02:30", "2026-11-02T07:30:00.000Z", "2026-10-25T00:30:00.000Z"],
    ["America/New_York", "2026-11-01T06:30:45.123456Z", "2026-03-08T02:30", "2026-11-02T13:30:00.000Z", "2026-11-01T05:30:00.000Z"],
  ])("preserves the second repeated hour and rejects nonexistent local time in %s", (zone, original, gap, changed, old) => {
    const value = probe(zone, original, gap);
    expect(value.original).toBe(original);
    expect(value.end).toBe("2026-11-02T12:00:45.123456Z");
    expect(value.oldRoundTrip).toBe(old);
    expect(value.changed).toBe(changed);
    expect(value.gapRejected).toBe(true);
    expect(value.crossInputReversed).toBe(true);
    expect(value.crossDuration).toBe(30 * 60 * 1000);
  });
  it("preserves seconds and precision independently of a DST zone", () => {
    const original = "2026-10-25T01:30:45.123456Z";
    const value = probe("UTC", original, "2026-02-30T10:00");
    expect(value.original).toBe(original);
    expect(value.gapRejected).toBe(true);
  });
});
