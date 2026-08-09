import { describe, it, expect } from "vitest";
import { generateRSS } from "../src/rss.js";
import type { Page, SiteConfig } from "../src/types.js";

const config: SiteConfig = {
  title: "My Blog",
  description: "A blog about code",
  baseUrl: "http://example.com",
  sourceDir: "/src",
  templateDir: "/tmpl",
  outputDir: "/out",
};

function makePage(title: string, date: string, html: string, draft = false): Page {
  return {
    frontmatter: { title, date, tags: ["test"] },
    content: "",
    html,
    slug: title.toLowerCase().replace(/\s/g, "-"),
    sourcePath: "/src/post.md",
    outputPath: "/out/post.html",
    isDraft: draft,
  };
}

describe("generateRSS", () => {
  it("generates valid RSS XML", () => {
    const pages = [makePage("Hello", "2024-01-01", "<p>Content</p>")];
    const rss = generateRSS(pages, config);
    expect(rss).toContain('<?xml version="1.0"');
    expect(rss).toContain("<rss version=\"2.0\"");
    expect(rss).toContain("<channel>");
    expect(rss).toContain("<title>My Blog</title>");
    expect(rss).toContain("<description>A blog about code</description>");
    expect(rss).toContain("<link>http://example.com</link>");
  });

  it("includes item entries for posts", () => {
    const pages = [makePage("First Post", "2024-01-01", "<p>Hello World</p>")];
    const rss = generateRSS(pages, config);
    expect(rss).toContain("<item>");
    expect(rss).toContain("<title>First Post</title>");
    expect(rss).toContain("<link>http://example.com/first-post.html</link>");
    expect(rss).toContain("<guid");
    expect(rss).toContain("<category>test</category>");
  });

  it("excludes draft posts", () => {
    const pages = [
      makePage("Published", "2024-01-01", "<p>Visible</p>", false),
      makePage("Draft", "2024-01-01", "<p>Hidden</p>", true),
    ];
    const rss = generateRSS(pages, config);
    expect(rss).toContain("Published");
    expect(rss).not.toContain("Draft");
  });

  it("sorts posts by date descending", () => {
    const pages = [
      makePage("Old", "2023-01-01", "<p>old</p>"),
      makePage("New", "2025-01-01", "<p>new</p>"),
    ];
    const rss = generateRSS(pages, config);
    const newIdx = rss.indexOf("New");
    const oldIdx = rss.indexOf("Old");
    expect(newIdx).toBeLessThan(oldIdx);
  });

  it("escapes XML special characters", () => {
    const pages = [
      makePage("A & B < C > D", "2024-01-01", '<p>x "y" & z</p>'),
    ];
    const rss = generateRSS(pages, config);
    expect(rss).toContain("A &amp; B &lt; C &gt; D");
    expect(rss).toContain("&quot;");
  });

  it("truncates long descriptions", () => {
    const longHtml = "<p>" + "a".repeat(1000) + "</p>";
    const pages = [makePage("Long", "2024-01-01", longHtml)];
    const rss = generateRSS(pages, config);
    const descStart = rss.indexOf("<description>");
    const descEnd = rss.indexOf("</description>", descStart);
    const desc = rss.slice(descStart + 13, descEnd);
    expect(desc.length).toBeLessThanOrEqual(500);
  });

  it("includes lastBuildDate", () => {
    const pages = [makePage("Post", "2024-01-01", "<p>x</p>")];
    const rss = generateRSS(pages, config);
    expect(rss).toContain("<lastBuildDate>");
  });

  it("limits items to 20", () => {
    const pages = Array.from({ length: 25 }, (_, i) =>
      makePage(`Post ${i}`, "2024-01-01", "<p>x</p>"),
    );
    const rss = generateRSS(pages, config);
    const itemCount = (rss.match(/<item>/g) || []).length;
    expect(itemCount).toBeLessThanOrEqual(20);
  });
});
