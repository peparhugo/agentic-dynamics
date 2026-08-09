import { describe, it, expect, beforeAll } from "vitest";
import { initMarked, markdownToHtml } from "../src/lib/markdown";

describe("markdownToHtml", () => {
  beforeAll(() => {
    initMarked();
  });

  it("converts basic markdown to HTML", () => {
    const result = markdownToHtml("# Hello\n\nWorld");
    expect(result).toContain("<h1");
    expect(result).toContain("Hello");
    expect(result).toContain("<p>World</p>");
  });

  it("renders fenced code blocks with syntax highlighting", () => {
    const result = markdownToHtml("```typescript\nconst x: number = 1;\n```");
    expect(result).toContain("<pre>");
    expect(result).toContain("language-typescript");
    expect(result).toContain("hljs");
  });

  it("renders code blocks without highlighting for unknown languages", () => {
    const result = markdownToHtml("```unknownlang\nsome code\n```");
    expect(result).toContain("<pre><code>");
    expect(result).not.toContain("language-unknownlang");
  });

  it("supports inline code", () => {
    const result = markdownToHtml("Use `const` keyword.");
    expect(result).toContain("<code>const</code>");
  });

  it("supports bold and italic", () => {
    const result = markdownToHtml("**bold** and *italic*");
    expect(result).toContain("<strong>bold</strong>");
    expect(result).toContain("<em>italic</em>");
  });

  it("supports links", () => {
    const result = markdownToHtml("[click here](https://example.com)");
    expect(result).toContain('<a href="https://example.com">');
  });

  it("handles empty input", () => {
    const result = markdownToHtml("");
    expect(result).toBe("");
  });

  it("handles HTML in code blocks safely", () => {
    const result = markdownToHtml("```\n<div>raw html</div>\n```");
    expect(result).toContain("&lt;div&gt;");
  });
});
