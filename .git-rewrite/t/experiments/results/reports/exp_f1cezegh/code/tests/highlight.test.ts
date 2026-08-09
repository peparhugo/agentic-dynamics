import { describe, it, expect } from "vitest";
import { markdownToHtml } from "../src/highlight";

describe("markdownToHtml (syntax highlighting)", () => {
  it("converts basic markdown to HTML", () => {
    const html = markdownToHtml("# Hello\n\nWorld");
    expect(html).toContain("<h1>Hello</h1>");
    expect(html).toContain("<p>World</p>");
  });

  it("highlights code blocks with language", () => {
    const html = markdownToHtml(
      '```typescript\nconst x: number = 42;\n```'
    );
    expect(html).toContain("hljs");
    expect(html).toContain("language-typescript");
  });

  it("handles code blocks without language", () => {
    const html = markdownToHtml("```\nplain code\n```");
    expect(html).toContain("<pre>");
    expect(html).toContain("<code>");
  });

  it("handles inline code", () => {
    const html = markdownToHtml("Use `const` keyword");
    expect(html).toContain("<code>const</code>");
  });

  it("handles GFM tables", () => {
    const html = markdownToHtml("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(html).toContain("<table>");
    expect(html).toContain("<td>1</td>");
  });

  it("handles bold and italic", () => {
    const html = markdownToHtml("**bold** and *italic*");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<em>italic</em>");
  });

  it("handles empty string", () => {
    const html = markdownToHtml("");
    expect(html).toBe("");
  });
});
