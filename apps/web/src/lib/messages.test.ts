import { describe, expect, it } from "vitest";
import { messages } from "./messages";

function resourceKeys(value: object, prefix = ""): string[] {
  return Object.entries(value).flatMap(([key, item]) => {
    const path = `${prefix}${key}`;
    return item !== null && typeof item === "object"
      ? resourceKeys(item, `${path}.`)
      : [path];
  }).sort();
}

describe("workspace translations", () => {
  it("provides every English resource in German as well", () => {
    expect(resourceKeys(messages.de)).toEqual(resourceKeys(messages.en));
  });
});
