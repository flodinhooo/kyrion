import { describe, expect, it } from "vitest";
import { changeHaEntities, isHaPreview, isHaSelection } from "./home-assistant-contracts";

const power = { key: "a".repeat(64), name: "Fixture lamp", state: "off", supportsPower: true };
const second = { ...power, key: "b".repeat(64) };
const source = { key: "c".repeat(64), name: "Fixture", sourceRoom: null, entities: [power, second] };
const choice = { key: source.key, entityKeys: [power.key], allowControl: true, overrideRoom: false, roomId: null };

describe("Home Assistant selection boundary", () => {
  it("rejects duplicate or raw provider identifiers in preview and selection", () => {
    expect(isHaPreview({ revision: 0, devices: [source] })).toBe(true);
    expect(isHaPreview({ revision: 0, devices: [source, source] })).toBe(false);
    expect(isHaPreview({ revision: 0, devices: [{ ...source, key: "light.private" }] })).toBe(false);
    expect(isHaSelection({ revision: 1, devices: [choice, choice] })).toBe(false);
    expect(isHaSelection({ revision: 1, devices: [{ ...choice, entityKeys: [power.key, power.key] }] })).toBe(false);
  });
  it("clears control consent when the selected power entity becomes ambiguous", () => {
    expect(changeHaEntities(choice, source, [power.key, second.key]).allowControl).toBe(false);
    expect(changeHaEntities(choice, source, []).allowControl).toBe(false);
    expect(() => changeHaEntities(choice, source, ["d".repeat(64)])).toThrow("HA_INVALID_SELECTION");
    expect(changeHaEntities({ ...choice, allowControl: false }, source, [power.key]).allowControl).toBe(false);
  });
});
