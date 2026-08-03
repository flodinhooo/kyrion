import { describe, expect, it } from "vitest";
import { createConversationTitle } from "./title";

describe("conversation titles", () => {
  it("always capitalizes the first letter", () => {
    expect(createConversationTitle("wie funktioniert das?", "de")).toBe("Wie funktioniert das?");
    expect(createConversationTitle("über meinen glauben sprechen", "de")).toBe("Über meinen glauben sprechen");
  });

  it("removes common markdown prefixes and uses the first sentence", () => {
    expect(createConversationTitle("# mein thema. Danach etwas anderes.", "de")).toBe("Mein thema.");
  });

  it("shortens long titles without cutting through the final word", () => {
    const title = createConversationTitle("dies ist eine sehr lange Unterhaltung über viele verschiedene Dinge und noch einige zusätzliche wichtige Details", "de");
    expect(title[0]).toBe("D");
    expect(title.length).toBeLessThanOrEqual(72);
    expect(title.endsWith("…")).toBe(true);
  });
});
