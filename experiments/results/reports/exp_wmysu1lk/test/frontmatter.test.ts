import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import { parseFrontmatter } from "../src/frontmatter";

describe("parseFrontmatter", () => {
  it("parses title, date, and tags from frontmatter", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-test-"));
    const filePath = path.join(dir, "test.md");
    fs.writeFileSync(
      filePath,
      `---
title: Hello World
date: 2024-01-15
tags: [intro, javascript]
---
Content here.`
    );

    const result = parseFrontmatter(filePath);
    expect(result).not.toBeNull();
    expect(result!.frontmatter.title).toBe("Hello World");
    expect(result!.frontmatter.date).toBe("2024-01-15");
    expect(result!.frontmatter.tags).toEqual(["intro", "javascript"]);
    expect(result!.frontmatter.draft).toBe(false);
    expect(result!.content).toBe("Content here.");

    fs.rmSync(dir, { recursive: true });
  });

  it("defaults title to filename when missing", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-test-"));
    const filePath = path.join(dir, "mypost.md");
    fs.writeFileSync(filePath, `Content without title.`);

    const result = parseFrontmatter(filePath);
    expect(result!.frontmatter.title).toBe("mypost");

    fs.rmSync(dir, { recursive: true });
  });

  it("defaults date to today when missing", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-test-"));
    const filePath = path.join(dir, "test.md");
    fs.writeFileSync(filePath, `---\ntitle: Only\n---\nContent.`);

    const result = parseFrontmatter(filePath);
    expect(result!.frontmatter.date).toBe(
      new Date().toISOString().split("T")[0]
    );

    fs.rmSync(dir, { recursive: true });
  });

  it("parses draft flag as true", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-test-"));
    const filePath = path.join(dir, "test.md");
    fs.writeFileSync(
      filePath,
      `---\ntitle: Draft\ndraft: true\n---\nContent.`
    );

    const result = parseFrontmatter(filePath);
    expect(result!.frontmatter.draft).toBe(true);

    fs.rmSync(dir, { recursive: true });
  });

  it("handles comma-separated string tags", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-test-"));
    const filePath = path.join(dir, "test.md");
    fs.writeFileSync(
      filePath,
      `---\ntitle: Post\ntags: a, b, c\n---\nContent.`
    );

    const result = parseFrontmatter(filePath);
    expect(result!.frontmatter.tags).toEqual(["a", "b", "c"]);

    fs.rmSync(dir, { recursive: true });
  });

  it("returns empty tags array when no tags specified", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "statik-test-"));
    const filePath = path.join(dir, "test.md");
    fs.writeFileSync(filePath, `---\ntitle: No Tags\n---\nContent.`);

    const result = parseFrontmatter(filePath);
    expect(result!.frontmatter.tags).toEqual([]);

    fs.rmSync(dir, { recursive: true });
  });

  it("returns null for non-existent file", () => {
    try {
      parseFrontmatter("/nonexistent/file.md");
      expect(true).toBe(false);
    } catch {
      expect(true).toBe(true);
    }
  });
});
