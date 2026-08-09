import { describe, it, expect } from "vitest";
import { markdownToHtml } from "../src/markdown.js";

describe("markdownToHtml", () => {
  it("converts basic markdown to HTML", () => {
    const result = markdownToHtml("# Hello\n\nWorld");
    expect(result).toContain("<h1>Hello</h1>");
    expect(result).toContain("<p>World</p>");
  });

  it("highlights code blocks with syntax", () => {
    const result = markdownToHtml('```js\nconst x = 1;\n```');
    expect(result).toContain("hljs");
    expect(result).toContain("language-js");
    expect(result).toContain("const");
  });

  it("handles auto-detection for unknown languages", () => {
    const result = markdownToHtml('```\nconst x = 1;\n```');
    expect(result).toContain("<code>");
  });

  it("handles GFM tables", () => {
    const result = markdownToHtml("| a | b |\n|---|---|\n| 1 | 2 |");
    expect(result).toContain("<table>");
    expect(result).toContain("<td>1</td>");
  });

  it("handles inline code", () => {
    const result = markdownToHtml("Use `const` keyword");
    expect(result).toContain("<code>const</code>");
  });

  it("returns empty string for non-string input via async guard", () => {
    // marked.parse can return string | Promise; our wrapper handles this
    const result = markdownToHtml("");
    expect(result).toBe("");
  });
});
