import { describe, it, expect } from "vitest";
import { markdownToHtml } from "../src/highlight.js";

describe("syntax highlighting", () => {
  it("converts markdown to HTML", () => {
    const html = markdownToHtml("# Title\n\nParagraph.");
    expect(html).toContain("<h1");
    expect(html).toContain("Title");
    expect(html).toContain("<p");
  });

  it("highlights code blocks", () => {
    const md = '```js\nconst x = 1;\n```';
    const html = markdownToHtml(md);
    expect(html).toContain("hljs");
    expect(html).toContain("const");
  });

  it("highlights python code", () => {
    const md = '```python\nprint("hello")\n```';
    const html = markdownToHtml(md);
    expect(html).toContain("hljs");
    expect(html).toContain("print");
  });

  it("auto-detects language when not specified", () => {
    const md = '```\nconst x = 1;\n```';
    const html = markdownToHtml(md);
    expect(html).toContain("hljs");
  });

  it("handles inline code", () => {
    const md = "Use `console.log()` for debugging.";
    const html = markdownToHtml(md);
    expect(html).toContain("<code>");
    expect(html).toContain("console.log()");
  });
});
