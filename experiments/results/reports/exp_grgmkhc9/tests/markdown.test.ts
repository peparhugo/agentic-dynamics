import { describe, it, expect } from "vitest";
import { markdownToHtml } from "../src/markdown";

describe("markdownToHtml", () => {
  it("converts basic markdown to HTML", () => {
    const html = markdownToHtml("# Hello\n\nWorld");
    expect(html).toContain("<h1>Hello</h1>");
    expect(html).toContain("<p>World</p>");
  });

  it("highlights code blocks with a language tag", () => {
    const md = "```javascript\nconst x = 1;\n```";
    const html = markdownToHtml(md);
    expect(html).toContain("language-javascript");
    expect(html).toContain("hljs");
  });

  it("works with fenced code without language", () => {
    const md = "```\nplain text\n```";
    const html = markdownToHtml(md);
    expect(html).toContain("<pre>");
    expect(html).toContain("<code");
  });

  it("converts inline code", () => {
    const html = markdownToHtml("Use `const` keyword.");
    expect(html).toContain("<code>const</code>");
  });

  it("handles empty input", () => {
    expect(markdownToHtml("")).toBe("");
  });
});
