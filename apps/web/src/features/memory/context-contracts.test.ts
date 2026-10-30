import {expect, it} from "vitest";
import {isContextSources, isPersonalMemory} from "./contracts";

it("validates bounded source metadata and rejects unsafe classifications and token counts", () => {
  const source = {
    kind: "personal_memory",
    id: "synthetic",
    privacy: "local_only",
    selected: true,
    reason: "confirmed",
    estimatedTokens: 12
  };
  expect(isContextSources([source])).toBe(true);
  expect(isContextSources([{...source, privacy: "public"}])).toBe(false);
  expect(isContextSources([{...source, estimatedTokens: -1}])).toBe(false);
  expect(isContextSources([{...source, estimatedTokens: Infinity}])).toBe(false);
  expect(isContextSources(Array(101).fill(source))).toBe(false);
});

it("accepts legacy memories and validates additive validity metadata", () => {
  const memory = {
    id: "synthetic",
    category: "project",
    content: "Synthetic",
    sensitivity: "standard",
    status: "confirmed",
    conflictsWithMemoryId: null
  };
  expect(isPersonalMemory(memory)).toBe(true);
  expect(isPersonalMemory({...memory, active: false, expiresAt: "2026-10-30T12:00:00Z"})).toBe(true);
  expect(isPersonalMemory({...memory, active: "false"})).toBe(false);
  expect(isPersonalMemory({...memory, expiresAt: "invalid"})).toBe(false);
});
