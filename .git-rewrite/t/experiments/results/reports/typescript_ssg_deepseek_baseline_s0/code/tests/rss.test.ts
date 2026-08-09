import { describe, it, expect } from "vitest";
import { generateRssXml } from "../src/rss.js";
import { SSGConfig, Page } from "../src/types.js";

const config: SSGConfig = {
  source: "",
  templates: "",
  output: "",
  siteTitle: "Test Site",
  siteUrl: "https://example.com",
  siteDescription: "A test site",
};

function makePage(title: string, date: Date, draft = false): Page {
  return {
    frontmatter: { title, date, draft, tags: [] },
    html: `<p>content for ${title}</p>`,
    content: `content for ${title}`,
    raw: "",
    slug: title.toLowerCase().replace(/\s/g, "-"),
    sourcePath: "",
    outputPath: "",
  };
}

describe("generateRssXml", () => {
  it("generates valid RSS XML", () => {
    const pages = [
      makePage("First Post", new Date("2024-01-01")),
      makePage("Second Post", new Date("2024-02-01")),
    ];

    const xml = generateRssXml(config, pages);
    expect(xml).toContain('<?xml version="1.0"');
    expect(xml).toContain("<rss version=\"2.0\"");
    expect(xml).toContain("<title>Test Site</title>");
    expect(xml).toContain("<title>First Post</title>");
    expect(xml).toContain("<title>Second Post</title>");
    expect(xml).toContain("<link>https://example.com/first-post.html</link>");
    expect(xml).toContain("<link>https://example.com/second-post.html</link>");
  });

  it("excludes draft pages", () => {
    const pages = [
      makePage("Published", new Date("2024-01-01"), false),
      makePage("Draft", new Date("2024-02-01"), true),
    ];

    const xml = generateRssXml(config, pages);
    expect(xml).toContain("<title>Published</title>");
    expect(xml).not.toContain("<title>Draft</title>");
  });

  it("excludes pages without dates", () => {
    const p: Page = {
      frontmatter: { title: "No Date", tags: [] },
      html: "",
      content: "",
      raw: "",
      slug: "no-date",
      sourcePath: "",
      outputPath: "",
    };

    const xml = generateRssXml(config, [p]);
    expect(xml).not.toContain("No Date");
  });

  it("sorts by date descending", () => {
    const pages = [
      makePage("Older", new Date("2024-01-01")),
      makePage("Newer", new Date("2024-06-01")),
    ];

    const xml = generateRssXml(config, pages);
    const newerIdx = xml.indexOf("Newer");
    const olderIdx = xml.indexOf("Older");
    expect(newerIdx).toBeLessThan(olderIdx);
  });

  it("limits to 20 items", () => {
    const pages = Array.from({ length: 25 }, (_, i) =>
      makePage(`Post ${i}`, new Date(`2024-01-${String(i + 1).padStart(2, "0")}`))
    );
    const xml = generateRssXml(config, pages);
    const count = (xml.match(/<item>/g) ?? []).length;
    expect(count).toBeLessThanOrEqual(20);
  });
});
