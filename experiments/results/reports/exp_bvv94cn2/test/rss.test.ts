import { describe, it, expect } from "vitest";
import { generateRss } from "../src/rss.js";
import type { Page, SiteConfig } from "../src/types.js";

function makePage(title: string, date: string, draft = false): Page {
  return {
    path: `/posts/${title.toLowerCase()}.md`,
    sourcePath: `${title.toLowerCase()}.md`,
    frontmatter: { title, date, tags: [] },
    content: "",
    html: "",
    url: `/${title.toLowerCase()}/`,
  };
}

const config: SiteConfig = {
  sourceDir: "/src",
  templateDir: "/tmpl",
  outputDir: "/out",
  siteTitle: "My Blog",
  siteUrl: "https://example.com",
};

describe("generateRss", () => {
  it("generates valid RSS XML", () => {
    const pages = [makePage("Post One", "2024-01-15")];
    const rss = generateRss(pages, config);

    expect(rss).toContain('<?xml version="1.0" encoding="UTF-8"?>');
    expect(rss).toContain('<rss version="2.0"');
    expect(rss).toContain("<title>My Blog</title>");
    expect(rss).toContain("<title>Post One</title>");
  });

  it("orders by date descending", () => {
    const pages = [
      makePage("Old", "2024-01-01"),
      makePage("New", "2024-06-15"),
    ];

    const rss = generateRss(pages, config);
    const newIdx = rss.indexOf("<title>New</title>");
    const oldIdx = rss.indexOf("<title>Old</title>");
    expect(newIdx).toBeLessThan(oldIdx);
  });

  it("excludes draft posts", () => {
    const pages = [
      makePage("Public", "2024-01-01"),
      { ...makePage("Draft", "2024-02-01"), frontmatter: { title: "Draft", date: "2024-02-01", tags: [], draft: true } },
    ];

    const rss = generateRss(pages, config);
    expect(rss).toContain("Public");
    expect(rss).not.toContain("Draft");
  });

  it("excludes posts without dates", () => {
    const pages = [
      { ...makePage("No Date", ""), frontmatter: { title: "No Date", tags: [] } },
      makePage("Has Date", "2024-01-01"),
    ];

    const rss = generateRss(pages, config);
    expect(rss).toContain("Has Date");
    expect(rss).not.toContain("No Date");
  });

  it("escapes XML special characters", () => {
    const pages = [
      {
        ...makePage("A & B", "2024-01-01"),
        frontmatter: { title: "Title <b> & \"quotes\"", date: "2024-01-01", tags: [] },
      },
    ];

    const rss = generateRss(pages, config);
    expect(rss).toContain("Title &lt;b&gt; &amp; &quot;quotes&quot;");
  });

  it("limits to 20 items", () => {
    const pages = Array.from({ length: 25 }, (_, i) =>
      makePage(`Post ${i}`, `2024-${String((i % 12) + 1).padStart(2, "0")}-${String(Math.floor(i / 12) + 1).padStart(2, "0")}`)
    );

    const rss = generateRss(pages, config);
    const itemCount = (rss.match(/<item>/g) || []).length;
    expect(itemCount).toBe(20);
  });
});
