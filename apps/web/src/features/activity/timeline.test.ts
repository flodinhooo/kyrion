import { describe, expect, it } from "vitest";
import { executionDuration } from "./timeline";
import type { ActivityEvent } from "./contracts";

const event = (eventType: string, occurredAt: string): ActivityEvent => ({ id: eventType, eventType, occurredAt,
  category: "CAPABILITY", status: "SUCCEEDED", actorType: "USER", actorId: null, source: "web", correlationId: "id", summaryCode: "action.succeeded" });
describe("action execution duration", () => {
  it("uses real recorded boundaries and refuses incomplete or truncated evidence", () => {
    const events = [event("action.proposed", "2026-09-06T10:00:00Z"), event("action.completed", "2026-09-06T10:00:00.684Z")];
    expect(executionDuration(events)).toBe(684);
    expect(executionDuration(events, true)).toBeNull();
    expect(executionDuration(events.slice(1))).toBeNull();
    expect(executionDuration(events.slice(0, 1))).toBeNull();
  });
});
