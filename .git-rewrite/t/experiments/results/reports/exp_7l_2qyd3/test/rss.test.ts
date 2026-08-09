import { describe, it, expect } from "vitest";
import { generateRSS } from "../src/rss.js";
import type { Page } from "../src/types.js";

describe("generateRSS", () => {
  const opts = {
    title: "Test Blog",
    description: "A test blog for RSS",
    baseUrl: "https://example.com",
    author: "Test Author",
  };

  it("generates RSS feed XML", () => {
    const pages: Page[] = [
      {
        frontmatter: { title: "Hello", date: "2024-06-01" },
        content: "<p>Hello world</p>",
        slug: "hello",
        sourcePath: "hello.md",
        outputPath: "",
        html: "",
      },
    ];

    const xml = generateRSS(pages, opts);
    expect(xml).toContain("<?xml");
    expect(xml).toContain("<rss");
    expect(xml).toContain("<title>Hello</title>");
    expect(xml).toContain("https://example.com/hello/");
  });

  it("includes channel metadata", () => {
    const xml = generateRSS([], opts);
    expect(xml).toContain("<title>Test Blog</title>");
    expect(xml).toContain("<description>A test blog for RSS</description>");
    expect(xml).toContain("https://example.com");
  });

  it("uses current date when no pages have dates", () => {
    const pages: Page[] = [
      {
        frontmatter: { title: "No Date" },
        content: "<p>No date</p>",
        slug: "nodate",
        sourcePath: "nodate.md",
        outputPath: "",
        html: "",
      },
    ];

    const xml = generateRSS(pages, opts);
    expect(xml).toContain("<rss");
    expect(xml).toContain("<title>No Date</title>");
  });
});
