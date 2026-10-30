import {describe, expect, it} from "vitest";
import {parseEvent} from "./api-chat-transport";

describe("normalized multi-provider stream validation", () => {
  it("accepts legacy text events and new provider/usage metadata", () => {
    expect(parseEvent('{"type":"message.delta","messageId":"m","delta":"OK"}')).toEqual({
      type: "message.delta",
      messageId: "m",
      delta: "OK"
    });
    expect(parseEvent('{"type":"usage","usage":{"inputTokens":4,"outputTokens":2,"totalTokens":6}}')).toMatchObject({usage: {totalTokens: 6}});
    expect(parseEvent('{"type":"model.selected","provider":"gemini","modelId":"official-id","profileId":"configured"}')).toMatchObject({provider: "gemini"});
    expect(parseEvent('{"type":"error","code":"RATE_LIMITED"}')).toEqual({type: "error", code: "RATE_LIMITED"});
  });
  it.each(['null', '{}', '{"type":"usage","usage":{"inputTokens":-1}}',
    '{"type":"message.delta","delta":42}', '{"type":"error","code":"SECRET_PROVIDER_BODY"}',
    '{"type":"tool.call","toolCall":{"name":"execute"}}'])("rejects malformed or executable browser events: %s", raw => {
    expect(() => parseEvent(raw)).toThrow();
  });
});
