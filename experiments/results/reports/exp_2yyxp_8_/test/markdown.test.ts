import { describe, it, expect } from "vitest";
import { renderMarkdown } from "../src/markdown";

describe("renderMarkdown", () => {
  it("converts basic markdown to HTML", () => {
    const html = renderMarkdown("# Hello World");
    expect(html).toContain("<h1>");
    expect(html).toContain("Hello World");
  });

  it("handles bold and italic", () => {
    const html = renderMarkdown("**bold** and *italic*");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<em>italic</em>");
  });

  it("handles links", () => {
    const html = renderMarkdown("[click here](https://example.com)");
    expect(html).toContain('<a href="https://example.com">');
    expect(html).toContain("click here");
  });

  it("handles unordered lists", () => {
    const html = renderMarkdown("- one\n- two\n- three");
    expect(html).toContain("<ul>");
    expect(html).toContain("<li>one</li>");
    expect(html).toContain("<li>two</li>");
    expect(html).toContain("<li>three</li>");
  });

  it("applies syntax highlighting to fenced code blocks", () => {
    const html = renderMarkdown('```typescript\nconst x: number = 1;\n```');
    expect(html).toContain("hljs");
    expect(html).toContain("language-typescript");
    expect(html).toContain("<pre>");
    expect(html).toContain("<code");
  });

  it("handles code blocks without language", () => {
    const html = renderMarkdown("```\nplain text\n```");
    expect(html).toContain("<pre>");
    expect(html).toContain("<code>");
    expect(html).toContain("plain text");
    expect(html).not.toContain("hljs");
  });

  it("escapes HTML in unhighlighted code blocks", () => {
    const html = renderMarkdown("```\n<div>text</div>\n```");
    expect(html).toContain("&lt;div&gt;text&lt;/div&gt;");
  });

  it("handles blockquotes", () => {
    const html = renderMarkdown("> quoted text");
    expect(html).toContain("<blockquote>");
    expect(html).toContain("quoted text");
  });
});
