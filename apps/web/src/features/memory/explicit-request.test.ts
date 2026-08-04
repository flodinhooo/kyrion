import { describe, expect, it } from "vitest";
import { explicitMemoryStatement } from "./explicit-request";

describe("explicitMemoryStatement", () => {
  it("accepts explicit German requests", () => {
    expect(explicitMemoryStatement("Merke dir: Kyrion ist mein Projekt", "de")).toBe("Kyrion ist mein Projekt");
    expect(explicitMemoryStatement("Bitte merke dir das, ich bevorzuge kurze Antworten", "de")).toBe("ich bevorzuge kurze Antworten");
  });

  it("accepts explicit English requests", () => {
    expect(explicitMemoryStatement("Remember this: Kyrion is my project", "en")).toBe("Kyrion is my project");
    expect(explicitMemoryStatement("Please remember, I prefer concise answers", "en")).toBe("I prefer concise answers");
  });

  it("does not infer memory from ordinary conversation", () => {
    expect(explicitMemoryStatement("Kyrion is my project", "en")).toBeNull();
    expect(explicitMemoryStatement("Ich arbeite an Kyrion", "de")).toBeNull();
  });
});
