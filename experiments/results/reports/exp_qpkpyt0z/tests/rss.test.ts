import { describe, it, expect } from "vitest";
import { generateRss } from "../src/rss.js";
import type { Page } from "../src/types.js";
import { makeConfig } from "./helpers.js";

function makePage(title: string, date: string, url: string, draft = false): Page {
  return {
    path: "",
    frontmatter: { title, date },
    content: "Content for " + title,
    html: "<p>Content</p>",
    url,
    isDraft: draft,
  };
}

describe("generateRss", () => {
  it("generates valid RSS XML", () => {
    const pages: Page[] = [
      makePage("Post One", "2024-01-15", "/posts/one/index.html"),
      makePage("Post Two", "2024-02-20", "/posts/two/index.html"),
    ];
    const config = makeConfig({ siteTitle: "Test", siteUrl: "https://example.com" });
    const rss = generateRss(pages, config);

    expect(rss).toContain('<?xml version="1.0"');
    expect(rss).toContain("<rss version=\"2.0\"");
    expect(rss).toContain("<title>Test</title>");
    expect(rss).toContain("<link>https://example.com</link>");
    expect(rss).toContain("Post One");
    expect(rss).toContain("Post Two");
  });

  it("excludes draft pages", () => {
    const pages: Page[] = [
      makePage("Published", "2024-01-15", "/pub/index.html", false),
      makePage("Draft", "2024-02-20", "/draft/index.html", true),
    ];
    const config = makeConfig();
    const rss = generateRss(pages, config);

    expect(rss).toContain("Published");
    expect(rss).not.toContain("Draft");
  });

  it("sorts by date descending", () => {
    const pages: Page[] = [
      makePage("Old", "2023-01-01", "/old/index.html"),
      makePage("New", "2025-01-01", "/new/index.html"),
    ];
    const config = makeConfig();
    const rss = generateRss(pages, config);

    const oldIdx = rss.indexOf("Old");
    const newIdx = rss.indexOf("New");
    expect(newIdx).toBeLessThan(oldIdx);
  });

  it("escapes XML special characters", () => {
    const pages: Page[] = [
      makePage("Foo & Bar < Baz", "2024-01-01", "/test/index.html"),
    ];
    const config = makeConfig();
    const rss = generateRss(pages, config);

    expect(rss).toContain("Foo &amp; Bar &lt; Baz");
    expect(rss).not.toContain("Foo & Bar < Baz");
  });
});
