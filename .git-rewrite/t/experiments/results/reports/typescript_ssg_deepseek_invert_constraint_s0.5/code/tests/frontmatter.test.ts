import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { parseFrontmatter, renderMarkdown } from "../src/utils.js";
import { join } from "node:path";
import { writeFileSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

describe("parseFrontmatter", () => {
  it("parses title, date, tags, and draft from YAML frontmatter", () => {
    const post = parseFrontmatter(join(__dirname, "fixtures/content/hello-world.md"));
    assert.equal(post.title, "Hello World");
    assert.deepEqual(post.tags, ["intro", "meta"]);
    assert.equal(post.draft, false);
    assert.ok(post.date instanceof Date);
    assert.equal(post.date!.toISOString().split("T")[0], "2025-01-15");
    assert.equal(post.slug, "hello-world");
    assert.ok(post.content.includes("# Hello World"));
  });

  it("defaults title to slugified filename when no title in frontmatter", () => {
    const tmpDir = join(__dirname, "fixtures/content");
    const tmpFile = join(tmpDir, "no-title.md");
    writeFileSync(tmpFile, "---\ntags: [a]\n---\nContent here.");
    try {
      const post = parseFrontmatter(tmpFile);
      assert.equal(post.title, "no-title");
    } finally {
      rmSync(tmpFile);
    }
  });

  it("supports comma-separated tags string", () => {
    const tmpDir = join(__dirname, "fixtures/content");
    const tmpFile = join(tmpDir, "csv-tags.md");
    writeFileSync(tmpFile, "---\ntitle: T\ntags: a, b, c\n---\nContent.");
    try {
      const post = parseFrontmatter(tmpFile);
      assert.deepEqual(post.tags, ["a", "b", "c"]);
    } finally {
      rmSync(tmpFile);
    }
  });

  it("detects draft posts", () => {
    const post = parseFrontmatter(join(__dirname, "fixtures/content/draft-post.md"));
    assert.equal(post.draft, true);
  });

  it("defaults draft to false when not specified", () => {
    const post = parseFrontmatter(join(__dirname, "fixtures/content/second-post.md"));
    assert.equal(post.draft, false);
  });

  it("defaults tags to empty array when not specified", () => {
    const tmpDir = join(__dirname, "fixtures/content");
    const tmpFile = join(tmpDir, "no-tags.md");
    writeFileSync(tmpFile, "---\ntitle: No Tags\n---\nContent.");
    try {
      const post = parseFrontmatter(tmpFile);
      assert.deepEqual(post.tags, []);
    } finally {
      rmSync(tmpFile);
    }
  });
});

describe("renderMarkdown", () => {
  it("converts markdown to HTML", () => {
    const html = renderMarkdown("# Hello\n\nWorld");
    assert.ok(html.includes("<h1>Hello</h1>"));
    assert.ok(html.includes("<p>World</p>"));
  });

  it("applies syntax highlighting to code blocks", () => {
    const html = renderMarkdown('```js\nconst x = 1;\n```');
    assert.ok(html.includes("hljs"), "should contain highlight.js classes");
  });

  it("escapes inline HTML", () => {
    const html = renderMarkdown('<script>alert("xss")</script>');
    assert.ok(!html.includes("<script>"));
  });
});
