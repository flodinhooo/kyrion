import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { MarkdownMessage } from "./markdown-message";

describe("MarkdownMessage", () => {
  it("renders fenced code, lists and safe external links", () => {
    const html = renderToStaticMarkup(<MarkdownMessage>{`## Beispiel

- erster Punkt

\`\`\`ts
const greeting = "Hallo";
\`\`\`

[Dokumentation](https://example.com)`}</MarkdownMessage>);
    expect(html).toContain("<h2>Beispiel</h2>");
    expect(html).toContain("<ul>");
    expect(html).toContain("<pre><code class=\"language-ts\"");
    expect(html).toContain("target=\"_blank\"");
    expect(html).toContain("rel=\"noreferrer\"");
  });
});
