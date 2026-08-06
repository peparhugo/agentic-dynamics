import { describe, it, expect } from "vitest";
import { createMarkdownRenderer } from "../src/markdown.js";

describe("createMarkdownRenderer", () => {
  const render = createMarkdownRenderer();

  it("renders basic markdown", () => {
    const html = render("# Title\n\nSome *emphasis*.");
    expect(html).toContain("<h1>Title</h1>");
    expect(html).toContain("<em>emphasis</em>");
  });

  it("highlights fenced code blocks with a known language", () => {
    const html = render('```ts\nconst x: number = 42;\n```');
    expect(html).toContain('class="hljs language-ts"');
    expect(html).toContain("hljs-"); // token spans, e.g. hljs-keyword
    expect(html).toContain("const");
  });

  it("auto-detects language when none is given", () => {
    const html = render('```\nfunction foo() { return 1; }\n```');
    expect(html).toContain("<pre><code");
    expect(html).toContain("hljs-");
  });

  it("escapes HTML inside code blocks", () => {
    const html = render('```html\n<script>alert(1)</script>\n```');
    expect(html).not.toContain("<script>alert(1)</script>");
  });
});
