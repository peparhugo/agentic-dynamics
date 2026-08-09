import { describe, it, expect } from "vitest";
import { generateRss, escapeXml } from "../src/rss.js";
import type { Page, PageMeta } from "../src/types.js";

function page(url: string, meta: Partial<PageMeta> = {}, html = "<p>body</p>"): Page {
  return {
    sourcePath: "x.md",
    slug: "x",
    outFile: "x/index.html",
    url,
    html,
    meta: {
      title: "X",
      date: new Date("2026-01-01"),
      tags: [],
      draft: false,
      layout: "default",
      extra: {},
      ...meta,
    },
  };
}

const site = { title: "Blog & Co", baseUrl: "https://example.com/", description: "d" };

describe("generateRss", () => {
  it("includes dated non-draft pages, newest first", () => {
    const xml = generateRss(
      [
        page("/old/", { title: "Old", date: new Date("2026-01-01") }),
        page("/new/", { title: "New", date: new Date("2026-02-01") }),
      ],
      site
    );
    expect(xml.indexOf("<title>New</title>")).toBeLessThan(xml.indexOf("<title>Old</title>"));
    expect(xml).toContain("<link>https://example.com/new/</link>");
    expect(xml).toContain("<pubDate>Sun, 01 Feb 2026 00:00:00 GMT</pubDate>");
  });

  it("excludes drafts and undated pages", () => {
    const xml = generateRss(
      [
        page("/draft/", { title: "Draft", draft: true }),
        page("/nodate/", { title: "NoDate", date: null }),
      ],
      site
    );
    expect(xml).not.toContain("Draft");
    expect(xml).not.toContain("NoDate");
  });

  it("escapes XML in channel and item fields", () => {
    const xml = generateRss([page("/a/", { title: 'Tags <&> "quoted"' })], site);
    expect(xml).toContain("<title>Blog &amp; Co</title>");
    expect(xml).toContain("Tags &lt;&amp;&gt; &quot;quoted&quot;");
  });

  it("emits tags as categories and body as CDATA description", () => {
    const xml = generateRss([page("/a/", { tags: ["ts", "web"] }, "<p>hi</p>")], site);
    expect(xml).toContain("<category>ts</category>");
    expect(xml).toContain("<category>web</category>");
    expect(xml).toContain("<![CDATA[<p>hi</p>]]>");
  });

  it("respects the item limit", () => {
    const pages = Array.from({ length: 5 }, (_, i) =>
      page(`/p${i}/`, { title: `P${i}`, date: new Date(2026, 0, i + 1) })
    );
    const xml = generateRss(pages, site, 2);
    expect(xml.match(/<item>/g)?.length).toBe(2);
  });
});

describe("escapeXml", () => {
  it("escapes all special characters", () => {
    expect(escapeXml(`<a href="x">&'</a>`)).toBe(
      "&lt;a href=&quot;x&quot;&gt;&amp;&apos;&lt;/a&gt;"
    );
  });
});
