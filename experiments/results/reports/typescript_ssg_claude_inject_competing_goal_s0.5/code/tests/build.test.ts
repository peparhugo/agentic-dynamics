import { describe, it, expect, afterEach } from "vitest";
import { promises as fs } from "node:fs";
import path from "node:path";
import { buildSite, collectTags, loadPages } from "../src/build.js";
import { generateRss } from "../src/rss.js";
import { makeFixture, type Fixture, DEFAULT_LAYOUT } from "./helpers.js";
import type { SiteConfig } from "../src/types.js";

let fixture: Fixture | null = null;
afterEach(async () => {
  await fixture?.cleanup();
  fixture = null;
});

function configFor(f: Fixture, overrides: Partial<SiteConfig> = {}): SiteConfig {
  return {
    sourceDir: f.sourceDir,
    templateDir: f.templateDir,
    outputDir: f.outputDir,
    siteTitle: "Test Site",
    siteUrl: "https://example.com",
    siteDescription: "A test site",
    includeDrafts: false,
    ...overrides,
  };
}

const POST = (title: string, date: string, tags: string[], draft = false) => `---
title: ${title}
date: ${date}
tags: [${tags.join(", ")}]
draft: ${draft}
---
Body of ${title}.
`;

describe("buildSite", () => {
  it("writes rendered pages, tag indexes, and an RSS feed", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": DEFAULT_LAYOUT,
      "templates/partials/nav.hbs": "<nav/>",
      "content/posts/a.md": POST("Post A", "2024-01-01", ["news"]),
      "content/posts/b.md": POST("Post B", "2024-02-01", ["news", "Tech Stuff"]),
    });
    const result = await buildSite(configFor(fixture));

    expect(result.pages).toHaveLength(2);
    const a = await fs.readFile(path.join(fixture.outputDir, "posts/a.html"), "utf8");
    expect(a).toContain("<title>Post A - Test Site</title>");
    expect(a).toContain("Body of Post A.");

    const newsTag = await fs.readFile(path.join(fixture.outputDir, "tags/news.html"), "utf8");
    expect(newsTag).toContain("Post A");
    expect(newsTag).toContain("Post B");
    // Tag slugification
    await fs.access(path.join(fixture.outputDir, "tags/tech-stuff.html"));

    const rss = await fs.readFile(path.join(fixture.outputDir, "feed.xml"), "utf8");
    expect(rss).toContain("<rss version=\"2.0\">");
    expect(rss).toContain("<title>Test Site</title>");
    expect(rss).toContain("https://example.com/posts/a.html");
    // Newest first in the feed
    expect(rss.indexOf("Post B")).toBeLessThan(rss.indexOf("Post A"));
  });

  it("skips drafts unless includeDrafts is set", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": DEFAULT_LAYOUT,
      "templates/partials/nav.hbs": "",
      "content/pub.md": POST("Pub", "2024-01-01", []),
      "content/wip.md": POST("WIP", "2024-01-02", [], true),
    });
    const without = await buildSite(configFor(fixture));
    expect(without.pages.map((p) => p.frontmatter.title)).toEqual(["Pub"]);
    expect(without.skippedDrafts).toBe(1);

    const withDrafts = await buildSite(configFor(fixture, { includeDrafts: true }));
    expect(withDrafts.pages.map((p) => p.frontmatter.title)).toEqual(["WIP", "Pub"]);
  });

  it("uses a page's custom layout when available, else default", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": "default:{{{content}}}",
      "templates/layouts/special.hbs": "special:{{{content}}}",
      "content/s.md": `---\ntitle: S\nlayout: special\n---\nx`,
      "content/m.md": `---\ntitle: M\nlayout: missing\n---\ny`,
    });
    await buildSite(configFor(fixture));
    const s = await fs.readFile(path.join(fixture.outputDir, "s.html"), "utf8");
    const m = await fs.readFile(path.join(fixture.outputDir, "m.html"), "utf8");
    expect(s).toMatch(/^special:/);
    expect(m).toMatch(/^default:/);
  });

  it("sorts pages newest-first and collects tags", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": "x",
      "content/old.md": POST("Old", "2020-01-01", ["t"]),
      "content/new.md": POST("New", "2025-01-01", ["t"]),
    });
    const { pages } = await loadPages(configFor(fixture));
    expect(pages.map((p) => p.frontmatter.title)).toEqual(["New", "Old"]);
    const tags = collectTags(pages);
    expect(Object.keys(tags)).toEqual(["t"]);
    expect(tags.t).toHaveLength(2);
  });
});

describe("generateRss", () => {
  it("escapes XML entities in titles and links", async () => {
    fixture = await makeFixture({
      "templates/layouts/default.hbs": "x",
      "content/amp.md": `---\ntitle: "Tom & Jerry <3"\ndate: 2024-01-01\n---\nhi`,
    });
    const { pages } = await loadPages(configFor(fixture));
    const xml = generateRss(configFor(fixture), pages);
    expect(xml).toContain("Tom &amp; Jerry &lt;3");
    expect(xml).not.toContain("Tom & Jerry <3");
  });
});
