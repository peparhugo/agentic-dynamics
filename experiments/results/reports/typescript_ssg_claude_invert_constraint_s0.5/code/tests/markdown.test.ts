import { describe, it, expect } from "vitest";
import { renderMarkdown } from "../src/markdown.js";

describe("renderMarkdown", () => {
  it("renders basic markdown", () => {
    const html = renderMarkdown("# Title\n\nSome *emphasis*.");
    expect(html).toContain("<h1>Title</h1>");
    expect(html).toContain("<em>emphasis</em>");
  });

  it("syntax-highlights fenced code blocks with a known language", () => {
    const html = renderMarkdown('```ts\nconst x: number = 1;\n```');
    expect(html).toContain('class="hljs language-ts"');
    expect(html).toMatch(/<span class="hljs-/);
  });

  it("escapes code for unknown languages without highlighting", () => {
    const html = renderMarkdown('```nosuchlang\n<b>&raw</b>\n```');
    expect(html).toContain("&lt;b&gt;&amp;raw&lt;/b&gt;");
    expect(html).not.toContain("language-nosuchlang");
  });

  it("does not double-wrap pre/code", () => {
    const html = renderMarkdown('```js\n1\n```');
    expect(html.match(/<pre>/g)?.length).toBe(1);
    expect(html.match(/<code/g)?.length).toBe(1);
  });
});
