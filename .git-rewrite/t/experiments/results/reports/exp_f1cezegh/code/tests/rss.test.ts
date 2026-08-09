import { describe, it, expect } from "vitest";
import { generateRSS } from "../src/rss";
import { Page, SiteConfig } from "../src/types";
import { parseFrontmatter } from "../src/frontmatter";

function makePage(file: string, raw: string): Page {
  const { meta, content } = parseFrontmatter(raw);
  return { path: file, url: file.replace(".md", ".html"), meta, content, raw };
}

const config: SiteConfig = {
  sourceDir: ".",
  outputDir: ".",
  templateDir: ".",
  siteTitle: "Test Blog",
  siteUrl: "https://example.com",
  siteDescription: "A test blog",
  port: 8080,
};

describe("generateRSS", () => {
  it("generates valid RSS XML", () => {
    const pages: Page[] = [
      makePage(
        "post1.md",
        `---
title: First Post
date: 2024-01-15
tags: [ts]
---
Content one.`
      ),
      makePage(
        "post2.md",
        `---
title: Second Post
date: 2024-02-20
tags: [js]
---
Content two.`
      ),
    ];

    const rss = generateRSS(pages, config);

    expect(rss).toContain("<?xml");
    expect(rss).toContain("<rss");
    expect(rss).toContain("Test Blog");
    expect(rss).toContain("First Post");
    expect(rss).toContain("Second Post");
    expect(rss).toContain("https://example.com");
  });

  it("excludes draft pages from RSS", () => {
    const pages: Page[] = [
      makePage(
        "post1.md",
        `---
title: Published
date: 2024-01-15
---
Content.`
      ),
      makePage(
        "draft.md",
        `---
title: Draft
date: 2024-01-15
draft: true
---
Hidden.`
      ),
    ];

    const rss = generateRSS(pages, config);
    expect(rss).toContain("Published");
    expect(rss).not.toContain("Draft");
  });

  it("excludes pages without dates from RSS", () => {
    const pages: Page[] = [
      makePage(
        "post1.md",
        `---
title: No Date
---
Content.`
      ),
      makePage(
        "post2.md",
        `---
title: With Date
date: 2024-05-10
---
Content.`
      ),
    ];

    const rss = generateRSS(pages, config);
    expect(rss).toContain("With Date");
    expect(rss).not.toContain("No Date");
  });

  it("returns valid RSS even with no pages", () => {
    const rss = generateRSS([], config);
    expect(rss).toContain("<?xml");
    expect(rss).toContain("<rss");
  });
});
