import {describe, expect, it} from "vitest";
import {isKnowledgeSource} from "./contracts";
import {knowledgeMessages} from "./messages";
import {parseEvent} from "@/features/chat/client/api-chat-transport";

const documentId = "11111111-1111-4111-8111-111111111111";
const source = {
  documentId, filename: "private.txt", excerpt: "Budget 42", page: null,
  startOffset: 0, endOffset: 9, reference: `kd:${documentId}:1:0`
};
describe("knowledge source contracts", () => {
  it("associates verified sources with the streamed answer", () => {
    const event = {type: "knowledge.sources", messageId: "answer-a", items: [source]};
    expect(parseEvent(JSON.stringify(event))).toEqual(event);
  });
  it("rejects external source references and oversized excerpts", () => {
    expect(isKnowledgeSource({...source, documentId: "../../private"})).toBe(false);
    expect(isKnowledgeSource({...source, reference: "https://untrusted.example/"})).toBe(false);
    expect(isKnowledgeSource({...source, excerpt: "x".repeat(2001)})).toBe(false);
    expect(() => parseEvent(JSON.stringify({
      type: "knowledge.sources",
      messageId: "a",
      items: [source, source, source, source]
    }))).toThrow();
  });
  it("has matching translated error codes", () => {
    expect(Object.keys(knowledgeMessages.de.errors).sort()).toEqual(Object.keys(knowledgeMessages.en.errors).sort());
  });
  it("preserves actionable local embedding failures in chat", () => {
    expect(parseEvent(JSON.stringify({type: "error", code: "KNOWLEDGE_EMBEDDING_SETUP_REQUIRED"})))
      .toEqual({type: "error", code: "KNOWLEDGE_EMBEDDING_SETUP_REQUIRED"});
  });
});
