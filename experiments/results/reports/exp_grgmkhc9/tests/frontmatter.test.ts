import { describe, it, expect } from "vitest";
import { parseFrontmatter, slugFromPath, isValidPage, collectPages } from "../src/frontmatter";
import path from "node:path";

const fixtures = path.resolve(__dirname, "../test-fixtures/content");

describe("parseFrontmatter", () => {
  it("parses YAML frontmatter with title, date, tags, draft, layout", () => {
    const result = parseFrontmatter(path.join(fixtures, "hello-world.md"));
    expect(result.frontmatter.title).toBe("Hello World");
    expect(result.frontmatter.date).toBe("2024-01-15");
    expect(result.frontmatter.tags).toEqual(["intro", "hello"]);
    expect(result.frontmatter.draft).toBeUndefined();
    expect(result.frontmatter.layout).toBe("default");
    expect(result.content).toContain("Hello World");
    expect(result.content).toContain("```javascript");
  });

  it("detects draft: true", () => {
    const result = parseFrontmatter(path.join(fixtures, "draft.md"));
    expect(result.frontmatter.draft).toBe(true);
    expect(result.frontmatter.title).toBe("Draft Post");
  });

  it("returns empty tags when not provided", () => {
    const fs = require("node:fs");
    const tmp = path.join(fixtures, "..", "content", "_notags.md");
    fs.writeFileSync(tmp, "---\ntitle: No Tags\n---\n\nContent.");
    try {
      const result = parseFrontmatter(tmp);
      expect(result.frontmatter.tags).toBeUndefined();
    } finally {
      fs.unlinkSync(tmp);
    }
  });
});

describe("slugFromPath", () => {
  it("derives slug from file path relative to source dir", () => {
    expect(slugFromPath("/src/content/hello-world.md", "/src/content")).toBe("hello-world");
  });

  it("handles nested directories", () => {
    expect(slugFromPath("/src/content/blog/post.md", "/src/content")).toBe("blog/post");
  });

  it("handles index files", () => {
    expect(slugFromPath("/src/content/blog/index.md", "/src/content")).toBe("blog");
  });
});

describe("isValidPage", () => {
  it("returns true for a page with title and no draft flag", () => {
    expect(isValidPage({ title: "Hello" })).toBe(true);
  });

  it("returns false for a draft page", () => {
    expect(isValidPage({ title: "Hello", draft: true })).toBe(false);
  });

  it("returns false for a page without a title", () => {
    expect(isValidPage({ title: "" })).toBe(false);
    expect(isValidPage({} as any)).toBe(false);
  });
});

describe("collectPages", () => {
  it("collects all .md files from source directory", async () => {
    const pages = await collectPages(fixtures);
    expect(pages.length).toBeGreaterThanOrEqual(3);
    const titles = pages.map((p) => p.frontmatter.title);
    expect(titles).toContain("Hello World");
    expect(titles).toContain("Another Post");
    expect(titles).toContain("Draft Post");
  });

  it("assigns correct slug", async () => {
    const pages = await collectPages(fixtures);
    const hello = pages.find((p) => p.frontmatter.title === "Hello World");
    expect(hello?.slug).toBe("hello-world");
  });
});
