import { describe, it, expect } from "vitest";
import { parseFrontmatter, collectMarkdownFiles, deriveUrlPath } from "../src/parser";
import fs from "fs";
import path from "path";
import os from "os";

describe("parseFrontmatter", () => {
  it("parses YAML frontmatter with title, date, tags, draft", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-test-"));
    const fp = path.join(dir, "post.md");
    fs.writeFileSync(
      fp,
      `---
title: Hello World
date: 2024-01-15
tags:
  - blog
  - typescript
draft: true
---
# Hello

This is content.`
    );

    const result = parseFrontmatter(fp);
    expect(result.frontmatter.title).toBe("Hello World");
    expect(result.frontmatter.date).toBeInstanceOf(Date);
    expect((result.frontmatter.date as Date).toISOString().startsWith("2024-01-15")).toBe(true);
    expect(result.frontmatter.tags).toEqual(["blog", "typescript"]);
    expect(result.frontmatter.draft).toBe(true);
    expect(result.content).toContain("# Hello");
    expect(result.content).toContain("This is content.");

    fs.rmSync(dir, { recursive: true });
  });

  it("handles missing frontmatter gracefully", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-test-"));
    const fp = path.join(dir, "plain.md");
    fs.writeFileSync(fp, "Just some markdown");

    const result = parseFrontmatter(fp);
    expect(result.frontmatter.title).toBeUndefined();
    expect(result.frontmatter.tags).toBeUndefined();
    expect(result.content).toBe("Just some markdown");

    fs.rmSync(dir, { recursive: true });
  });

  it("handles empty frontmatter", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-test-"));
    const fp = path.join(dir, "empty.md");
    fs.writeFileSync(
      fp,
      `---
---
Content only`
    );

    const result = parseFrontmatter(fp);
    expect(result.content.trim()).toBe("Content only");
    expect(result.frontmatter).toEqual({});

    fs.rmSync(dir, { recursive: true });
  });

  it("preserves arbitrary frontmatter keys", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-test-"));
    const fp = path.join(dir, "custom.md");
    fs.writeFileSync(
      fp,
      `---
title: Custom
template: post.hbs
custom_field: 42
---
Body`
    );

    const result = parseFrontmatter(fp);
    expect(result.frontmatter.template).toBe("post.hbs");
    expect(result.frontmatter.custom_field).toBe(42);

    fs.rmSync(dir, { recursive: true });
  });
});

describe("collectMarkdownFiles", () => {
  it("finds all .md files recursively", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-test-"));
    fs.mkdirSync(path.join(dir, "subdir"), { recursive: true });
    fs.writeFileSync(path.join(dir, "a.md"), "a");
    fs.writeFileSync(path.join(dir, "b.md"), "b");
    fs.writeFileSync(path.join(dir, "subdir", "c.md"), "c");
    fs.writeFileSync(path.join(dir, "notes.txt"), "txt");

    const files = collectMarkdownFiles(dir);
    expect(files.length).toBe(3);
    expect(files.some(f => f.endsWith("a.md"))).toBe(true);
    expect(files.some(f => f.endsWith("subdir/c.md") || f.endsWith("subdir\\c.md"))).toBe(true);

    fs.rmSync(dir, { recursive: true });
  });

  it("returns empty array for directory with no markdown", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-test-"));
    fs.writeFileSync(path.join(dir, "notes.txt"), "txt");

    const files = collectMarkdownFiles(dir);
    expect(files.length).toBe(0);

    fs.rmSync(dir, { recursive: true });
  });
});

describe("deriveUrlPath", () => {
  it("converts index.md to /", () => {
    expect(deriveUrlPath("/src/index.md", "/src")).toBe("/");
  });

  it("converts about.md to /about/", () => {
    expect(deriveUrlPath("/src/about.md", "/src")).toBe("/about/");
  });

  it("converts posts/hello.md to /posts/hello/", () => {
    expect(deriveUrlPath("/src/posts/hello.md", "/src")).toBe("/posts/hello/");
  });

  it("handles nested directories", () => {
    expect(deriveUrlPath("/src/a/b/c.md", "/src")).toBe("/a/b/c/");
  });
});
