import { describe, it, expect } from "vitest";
import { resolve } from "node:path";
import { loadTemplates, renderMarkdown, renderTemplate } from "../src/renderer.js";

describe("renderMarkdown", () => {
  it("renders basic markdown to HTML", () => {
    const html = renderMarkdown("# Hello\n\nWorld");
    expect(html).toContain("<h1>Hello</h1>");
    expect(html).toContain("<p>World</p>");
  });

  it("renders bold and italic", () => {
    const html = renderMarkdown("**bold** *italic*");
    expect(html).toContain("<strong>bold</strong>");
    expect(html).toContain("<em>italic</em>");
  });

  it("renders links", () => {
    const html = renderMarkdown("[link](http://example.com)");
    expect(html).toContain('<a href="http://example.com">link</a>');
  });

  it("renders fenced code blocks with syntax highlighting", () => {
    const html = renderMarkdown('```js\nconst x = 1;\n```');
    expect(html).toContain("hljs");
    expect(html).toContain("language-js");
    expect(html).toContain("const");
  });

  it("renders code blocks without language", () => {
    const html = renderMarkdown("```\nplain text\n```");
    expect(html).toContain("<code>plain text");
  });

  it("renders lists", () => {
    const html = renderMarkdown("- one\n- two\n- three");
    expect(html).toContain("<ul>");
    expect(html).toContain("<li>one</li>");
    expect(html).toContain("<li>two</li>");
    expect(html).toContain("<li>three</li>");
  });
});

describe("loadTemplates", () => {
  it("loads templates and layout from directory", async () => {
    const tmpl = await loadTemplates(resolve("tests/fixtures/templates"));
    expect(tmpl.layout).not.toBeNull();
    expect(tmpl.templates.has("post")).toBe(true);
    expect(tmpl.templates.has("index")).toBe(true);
    expect(tmpl.templates.has("tag")).toBe(true);
    expect(tmpl.partials.has("header")).toBe(true);
    expect(tmpl.partials.has("footer")).toBe(true);
  });
});

describe("renderTemplate", () => {
  it("renders post template with layout wrapping", async () => {
    const tmpl = await loadTemplates(resolve("tests/fixtures/templates"));
    const html = renderTemplate(tmpl, "post", {
      title: "Test",
      date: "2024-01-01",
      tags: ["a", "b"],
      content: "<p>body</p>",
      site: { title: "MySite" },
    });
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("<h1>Test</h1>");
    expect(html).toContain("<span class=\"tag\">a</span>");
    expect(html).toContain("<span class=\"tag\">b</span>");
    expect(html).toContain("MySite");
  });

  it("renders index template", async () => {
    const tmpl = await loadTemplates(resolve("tests/fixtures/templates"));
    const html = renderTemplate(tmpl, "index", {
      title: "Home",
      pages: [{ slug: "post1", frontmatter: { title: "Post One" } }],
    });
    expect(html).toContain("Post One");
    expect(html).toContain("/post1.html");
  });

  it("throws for missing template", async () => {
    const tmpl = await loadTemplates(resolve("tests/fixtures/templates"));
    expect(() => renderTemplate(tmpl, "nonexistent", {})).toThrow(
      'Template "nonexistent" not found',
    );
  });

  it("includes partials from layout", async () => {
    const tmpl = await loadTemplates(resolve("tests/fixtures/templates"));
    const html = renderTemplate(tmpl, "post", {
      title: "T",
      content: "C",
      site: { title: "S" },
    });
    expect(html).toContain("<header>");
    expect(html).toContain("<footer>");
  });
});
