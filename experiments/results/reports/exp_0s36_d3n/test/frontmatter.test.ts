import { describe, it, expect } from "vitest";
import path from "path";
import fs from "fs";
import {
  parseFrontmatter,
  resolvePages,
  getPublishedPages,
  getSortedPages,
  getTags,
} from "../src/frontmatter";

const fixturesDir = path.join(__dirname, "fixtures", "source");

describe("parseFrontmatter", () => {
  const filePath = path.join(fixturesDir, "posts", "hello-world.md");

  it("parses YAML frontmatter title", () => {
    const result = parseFrontmatter(filePath);
    expect(result.frontmatter.title).toBe("Hello World");
  });

  it("parses date from frontmatter", () => {
    const result = parseFrontmatter(filePath);
    expect(result.frontmatter.date).toBeDefined();
    expect(new Date(result.frontmatter.date!).getFullYear()).toBe(2024);
  });

  it("parses tags array from frontmatter", () => {
    const result = parseFrontmatter(filePath);
    expect(result.frontmatter.tags).toEqual(["javascript", "web"]);
  });

  it("parses draft flag from frontmatter", () => {
    const result = parseFrontmatter(filePath);
    expect(result.frontmatter.draft).toBe(false);
  });

  it("returns content without frontmatter", () => {
    const result = parseFrontmatter(filePath);
    expect(result.content).toContain("# Hello World");
    expect(result.content).toContain("console.log");
  });

  it("defaults draft to false when not specified", () => {
    const aboutPath = path.join(fixturesDir, "pages", "about.md");
    const result = parseFrontmatter(aboutPath);
    expect(result.frontmatter.draft).toBe(false);
  });

  it("parses custom frontmatter property like layout", () => {
    const aboutPath = path.join(fixturesDir, "pages", "about.md");
    const result = parseFrontmatter(aboutPath);
    expect(result.frontmatter.layout).toBe("page");
  });
});

describe("resolvePages", () => {
  it("resolves all markdown files recursively", () => {
    const pages = resolvePages(fixturesDir);
    expect(pages.length).toBe(3);
  });

  it("sets correct urls for files", () => {
    const pages = resolvePages(fixturesDir);
    const hello = pages.find((p) => p.frontmatter.title === "Hello World");
    expect(hello).toBeDefined();
    expect(hello!.url).toBe("/posts/hello-world/");
  });

  it("reads content from files", () => {
    const pages = resolvePages(fixturesDir);
    const hello = pages.find((p) => p.frontmatter.title === "Hello World");
    expect(hello!.content).toContain("# Hello World");
  });
});

describe("getPublishedPages", () => {
  it("filters out draft pages", () => {
    const pages = resolvePages(fixturesDir);
    const published = getPublishedPages(pages);
    expect(published.length).toBe(2);
    expect(
      published.every((p) => !p.frontmatter.draft)
    ).toBe(true);
  });

  it("includes non-draft pages", () => {
    const pages = resolvePages(fixturesDir);
    const published = getPublishedPages(pages);
    const titles = published.map((p) => p.frontmatter.title);
    expect(titles).toContain("Hello World");
    expect(titles).toContain("About");
    expect(titles).not.toContain("Draft Post");
  });
});

describe("getSortedPages", () => {
  it("sorts pages by date descending", () => {
    const pages = resolvePages(fixturesDir);
    const published = getPublishedPages(pages);
    const sorted = getSortedPages(published);
    expect(sorted.length).toBe(2);
  });

  it("pages without dates sort after dated pages", () => {
    const pages = resolvePages(fixturesDir);
    const all = getPublishedPages(pages);
    const sorted = getSortedPages(all);
    expect(sorted[0].frontmatter.date).toBeDefined();
  });
});

describe("getTags", () => {
  it("returns a map of tags to pages", () => {
    const pages = resolvePages(fixturesDir);
    const published = getPublishedPages(pages);
    const tags = getTags(published);
    expect(tags.has("javascript")).toBe(true);
    expect(tags.has("web")).toBe(true);
  });

  it("each tag maps to correct pages", () => {
    const pages = resolvePages(fixturesDir);
    const published = getPublishedPages(pages);
    const tags = getTags(published);
    const jsPages = tags.get("javascript")!;
    expect(jsPages.length).toBe(1);
    expect(jsPages[0].frontmatter.title).toBe("Hello World");
  });
});
