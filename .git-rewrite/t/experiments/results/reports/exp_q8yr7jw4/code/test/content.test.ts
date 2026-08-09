import { describe, it, expect } from "vitest";
import { parseDocument, renderMarkdown, makeExcerpt, normalizeFrontmatter } from "../src/content.js";

describe("frontmatter parsing", () => {
  it("parses title, date, tags, draft", () => {
    const doc = parseDocument(
      `---
title: Hello World
date: 2024-03-15
tags: [alpha, beta]
draft: true
---
Body text.`
    );
    expect(doc.frontmatter.title).toBe("Hello World");
    expect(doc.frontmatter.date).toBeInstanceOf(Date);
    expect(doc.frontmatter.date!.toISOString().slice(0, 10)).toBe("2024-03-15");
    expect(doc.frontmatter.tags).toEqual(["alpha", "beta"]);
    expect(doc.frontmatter.draft).toBe(true);
    expect(doc.body.trim()).toBe("Body text.");
  });

  it("handles missing frontmatter with fallback title", () => {
    const doc = parseDocument("Just markdown.", "my-file");
    expect(doc.frontmatter.title).toBe("my-file");
    expect(doc.frontmatter.date).toBeNull();
    expect(doc.frontmatter.tags).toEqual([]);
    expect(doc.frontmatter.draft).toBe(false);
    expect(doc.body).toBe("Just markdown.");
  });

  it("accepts comma-separated tag strings", () => {
    const fm = normalizeFrontmatter({ tags: "a, b , c" }, "x");
    expect(fm.tags).toEqual(["a", "b", "c"]);
  });

  it("accepts YAML list tags with mixed types and trims", () => {
    const fm = normalizeFrontmatter({ tags: [" a ", 1, ""] }, "x");
    expect(fm.tags).toEqual(["a", "1"]);
  });

  it("parses string dates and rejects invalid ones", () => {
    expect(normalizeFrontmatter({ date: "2020-01-02" }, "x").date!.getUTCFullYear()).toBe(2020);
    expect(normalizeFrontmatter({ date: "not a date" }, "x").date).toBeNull();
  });

  it("treats draft: 'true' string as draft, everything else as not", () => {
    expect(normalizeFrontmatter({ draft: "true" }, "x").draft).toBe(true);
    expect(normalizeFrontmatter({ draft: false }, "x").draft).toBe(false);
    expect(normalizeFrontmatter({}, "x").draft).toBe(false);
  });

  it("preserves extra frontmatter fields", () => {
    const fm = normalizeFrontmatter({ author: "Ada", layout: "special" }, "x");
    expect(fm.author).toBe("Ada");
    expect(fm.layout).toBe("special");
  });
});

describe("markdown rendering", () => {
  it("renders basic markdown", () => {
    const html = renderMarkdown("# Heading\n\nSome **bold** text.");
    expect(html).toContain("<h1");
    expect(html).toContain("<strong>bold</strong>");
  });

  it("syntax-highlights known languages", () => {
    const html = renderMarkdown("```js\nconst x = 1;\n```");
    expect(html).toContain('class="hljs language-js"');
    expect(html).toContain("hljs-keyword");
  });

  it("escapes code for unknown languages without highlighting", () => {
    const html = renderMarkdown("```nosuchlang\n<b>&raw</b>\n```");
    expect(html).toContain("&lt;b&gt;&amp;raw&lt;/b&gt;");
    expect(html).not.toContain("language-nosuchlang");
  });

  it("escapes code with no language tag", () => {
    const html = renderMarkdown("```\na < b\n```");
    expect(html).toContain("a &lt; b");
  });
});

describe("makeExcerpt", () => {
  it("strips markdown syntax and code blocks", () => {
    const md = "# Title\n\n```js\nconst hidden = true;\n```\n\nSome *emphasis* and [a link](http://x.test).";
    const excerpt = makeExcerpt(md);
    expect(excerpt).not.toContain("hidden");
    expect(excerpt).toContain("a link");
    expect(excerpt).not.toContain("[");
    expect(excerpt).not.toContain("*");
  });

  it("truncates long text with ellipsis", () => {
    const excerpt = makeExcerpt("word ".repeat(200), 50);
    expect(excerpt.length).toBeLessThanOrEqual(50);
    expect(excerpt.endsWith("…")).toBe(true);
  });
});
