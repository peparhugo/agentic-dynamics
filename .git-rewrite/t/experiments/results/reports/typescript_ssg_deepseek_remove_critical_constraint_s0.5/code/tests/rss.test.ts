import { describe, it, expect } from "vitest";
import { generateRss } from "../src/rss";
import { Page, SiteConfig } from "../src/types";

function makeConfig(overrides?: Partial<SiteConfig>): SiteConfig {
  return {
    sourceDir: ".",
    templateDir: ".",
    outputDir: ".",
    siteTitle: "Test Blog",
    siteUrl: "https://example.com",
    port: 3000,
    serve: false,
    watch: false,
    ...overrides,
  };
}

describe("generateRss", () => {
  it("generates valid RSS XML with items", () => {
    const pages: Page[] = [
      {
        frontmatter: { title: "Post One", date: "2024-01-01" },
        content: "First post content here",
        html: "",
        slug: "post-one",
        sourcePath: "",
      },
      {
        frontmatter: { title: "Post Two", date: "2024-06-15" },
        content: "Second post content",
        html: "",
        slug: "post-two",
        sourcePath: "",
      },
    ];

    const rss = generateRss(pages, makeConfig());

    expect(rss).toContain('<?xml version="1.0"');
    expect(rss).toContain("<rss version=\"2.0\"");
    expect(rss).toContain("<title>Test Blog</title>");
    expect(rss).toContain("<link>https://example.com</link>");
    expect(rss).toContain("<title>Post One</title>");
    expect(rss).toContain("<title>Post Two</title>");
    expect(rss).toContain("<link>https://example.com/post-one</link>");
    expect(rss).toContain("<link>https://example.com/post-two</link>");
    expect(rss).toContain("<description>");
  });

  it("excludes draft pages", () => {
    const pages: Page[] = [
      {
        frontmatter: { title: "Published", date: "2024-01-01", draft: false },
        content: "",
        html: "",
        slug: "published",
        sourcePath: "",
      },
      {
        frontmatter: { title: "Draft", date: "2024-06-01", draft: true },
        content: "",
        html: "",
        slug: "draft",
        sourcePath: "",
      },
    ];

    const rss = generateRss(pages, makeConfig());
    expect(rss).toContain("Published");
    expect(rss).not.toContain("Draft");
  });

  it("sorts items by date descending", () => {
    const pages: Page[] = [
      {
        frontmatter: { title: "Old", date: "2023-01-01" },
        content: "",
        html: "",
        slug: "old",
        sourcePath: "",
      },
      {
        frontmatter: { title: "New", date: "2024-01-01" },
        content: "",
        html: "",
        slug: "new",
        sourcePath: "",
      },
    ];

    const rss = generateRss(pages, makeConfig());
    const newIndex = rss.indexOf("New");
    const oldIndex = rss.indexOf("Old");
    expect(newIndex).toBeLessThan(oldIndex);
  });

  it("escapes XML special characters", () => {
    const pages: Page[] = [
      {
        frontmatter: { title: "A & B < C", date: "2024-01-01" },
        content: "x > y & z",
        html: "",
        slug: "escape",
        sourcePath: "",
      },
    ];

    const rss = generateRss(pages, makeConfig());
    expect(rss).toContain("A &amp; B &lt; C");
  });

  it("generates empty feed with no published pages", () => {
    const rss = generateRss([], makeConfig());
    expect(rss).toContain("<rss");
    expect(rss).not.toContain("<item>");
  });
});
