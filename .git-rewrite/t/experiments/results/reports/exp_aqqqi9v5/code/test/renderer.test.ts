import { describe, it, expect } from "vitest";
import { renderMarkdown } from "../src/renderer.js";

describe("renderMarkdown", () => {
  it("renders basic markdown", () => {
    const result = renderMarkdown("# Hello");
    expect(result).toContain("<h1");
    expect(result).toContain("Hello");
  });

  it("renders paragraphs", () => {
    const result = renderMarkdown("This is a paragraph.");
    expect(result).toContain("<p>");
    expect(result).toContain("This is a paragraph.");
  });

  it("renders bold and italic", () => {
    const result = renderMarkdown("**bold** and *italic*");
    expect(result).toContain("<strong>bold</strong>");
    expect(result).toContain("<em>italic</em>");
  });

  it("renders links", () => {
    const result = renderMarkdown("[link](https://example.com)");
    expect(result).toContain('<a href="https://example.com">');
    expect(result).toContain("link");
  });

  it("renders code spans", () => {
    const result = renderMarkdown("Use the `code` function.");
    expect(result).toContain("<code>code</code>");
  });

  it("renders fenced code blocks with syntax highlighting", () => {
    const result = renderMarkdown("```ts\nconst x = 1;\n```");
    expect(result).toContain("hljs");
    expect(result).toContain("language-ts");
    expect(result).toContain("language-ts");
    expect(result).toContain("x = ");
    expect(result).toContain("hljs-number");
  });

  it("renders fenced code blocks without language", () => {
    const result = renderMarkdown("```\nplain text\n```");
    expect(result).toContain("plain text");
  });

  it("renders unordered lists", () => {
    const result = renderMarkdown("- item 1\n- item 2");
    expect(result).toContain("<ul>");
    expect(result).toContain("<li>item 1</li>");
    expect(result).toContain("<li>item 2</li>");
  });

  it("renders ordered lists", () => {
    const result = renderMarkdown("1. first\n2. second");
    expect(result).toContain("<ol>");
    expect(result).toContain("<li>first</li>");
    expect(result).toContain("<li>second</li>");
  });

  it("renders blockquotes", () => {
    const result = renderMarkdown("> quoted text");
    expect(result).toContain("<blockquote>");
    expect(result).toContain("quoted text");
  });
});
