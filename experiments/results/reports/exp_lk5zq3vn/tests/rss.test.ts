import { describe, it, expect } from "vitest";
import { generateRss, escapeXml } from "../src/rss.js";
import type { Page, SiteConfig } from "../src/types.js";

const config: SiteConfig = {
  sourceDir: "c",
  templateDir: "t",
  outDir: "o",
  includeDrafts: false,
  baseUrl: "https://site.test/",
  siteTitle: "Feed & Co",
  siteDescription: "desc",
};

function page(title: string, date: string | null, urlPath: string): Page {
  return {
    sourcePath: "x.md",
    outPath: urlPath.slice(1),
    urlPath,
    raw: "",
    html: `<p>${title}</p>`,
    frontmatter: { title, date: date ? new Date(date) : null, tags: [], draft: false, layout: "default", extra: {} },
  };
}

describe("generateRss", () => {
  it("escapes XML entities in channel and items", () => {
    const rss = generateRss([page("A & B <ok>", "2026-01-01", "/a.html")], config);
    expect(rss).toContain("<title>Feed &amp; Co</title>");
    expect(rss).toContain("A &amp; B &lt;ok&gt;");
    expect(rss).toContain("&lt;p&gt;");
  });

  it("skips undated pages and strips trailing slash from base URL", () => {
    const rss = generateRss([page("Dated", "2026-01-01", "/d.html"), page("Undated", null, "/u.html")], config);
    expect(rss).toContain("https://site.test/d.html");
    expect(rss).not.toContain("Undated");
    expect(rss).not.toContain("site.test//");
  });

  it("caps at 20 items, newest first", () => {
    const pages = Array.from({ length: 25 }, (_, i) =>
      page(`P${i}`, `2026-01-${String(i + 1).padStart(2, "0")}`, `/p${i}.html`)
    );
    const rss = generateRss(pages, config);
    expect((rss.match(/<item>/g) ?? []).length).toBe(20);
    expect(rss).toContain("P24"); // newest kept
    expect(rss).not.toContain("<title>P0</title>"); // oldest dropped
  });

  it("escapeXml handles all five entities", () => {
    expect(escapeXml(`&<>"'`)).toBe("&amp;&lt;&gt;&quot;&apos;");
  });
});
