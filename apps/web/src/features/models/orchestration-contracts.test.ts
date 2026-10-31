import {expect, it} from "vitest";
import {isAiUsage} from "./orchestration-contracts";

const usage = {
  period: "2026-10", tokenLimit: 2000, costLimit: 0.1, currency: "USD",
  chargedTokens: 116, costsAreEstimates: true,
  rows: [{provider: "openai", profileId: "test", modelId: "synthetic", requests: 1, chargedTokens: 116,
    inputTokens: null, outputTokens: null, estimatedCost: null, currency: "USD", pending: 1,
    accountingState: "uncertain", unknownCosts: 1, costBasis: "reservation"}],
  openAttempts: [{id: "synthetic-attempt", period: "2026-09", provider: "openai", profileId: "test",
    state: "uncertain", chargedTokens: 116, estimatedCost: null, currency: "USD", errorCode: "REQUEST_TIMEOUT"}],
  openAttemptsTruncated: false,
};

it("retains unknown monetary costs and old-month open cases as distinct accounting data", () => {
  expect(isAiUsage(usage)).toBe(true);
});

it("rejects malformed and unbounded accounting details", () => {
  expect(isAiUsage({...usage, rows: [{...usage.rows[0], accountingState: "paid"}]})).toBe(false);
  expect(isAiUsage({...usage, rows: [{...usage.rows[0], unknownCosts: -1}]})).toBe(false);
  expect(isAiUsage({...usage, rows: [{...usage.rows[0], estimatedCost: NaN}]})).toBe(false);
  expect(isAiUsage({...usage, openAttempts: [{...usage.openAttempts[0], chargedTokens: -1}]})).toBe(false);
  expect(isAiUsage({...usage, openAttempts: Array(101).fill(usage.openAttempts[0])})).toBe(false);
});

it("accepts the previous API while allowing the UI to disclose missing accounting details", () => {
  expect(isAiUsage({period: "2026-10", tokenLimit: null, costLimit: null, currency: null,
    chargedTokens: 0, costsAreEstimates: true, rows: []})).toBe(true);
});
