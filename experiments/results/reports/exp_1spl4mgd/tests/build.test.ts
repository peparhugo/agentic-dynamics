import { describe, it, expect, beforeAll, afterAll } from "vitest";
import { buildSite } from "../src/build.js";
import { makeFixture, readOut, exists, type Fixture } from "./helpers.js";

describe("buildSite", () => {
  let fixture: Fixture;

  beforeAll(async () => {
    fixture = await makeFixture();
    await buildSite({
      sourceDir: fixture.sourceDir,
      templateDir: fixture.templateDir,
      outDir: fixture.outDir,
      site: { title: "Test Site", baseUrl: "https://example.com", description: "A test" },
    });
  });

  afterAll(() => fixture.cleanup());

  it("writes pretty URLs: index.md -> index.html, post.md -> post/index.html", async () => {
    expect(await exists(fixture, "index.html")).toBe(true);
    expect(await exists(fixture, "posts/hello/index.html")).toBe(true);
    expect(await exists(fixture, "posts/second/index.html")).toBe(true);
  });

  it("applies the layout named in frontmatter, with partials", async () => {
    const home = await readOut(fixture, "index.html");
    expect(home).toContain("<title>Home — Test Site</title>");
    expect(home).toContain('<header class="site-header">Test Site</header>');
    expect(home).toContain("<h1>Welcome</h1>");

    const post = await readOut(fixture, "posts/hello/index.html");
    expect(post).toContain('<article class="post">');
    expect(post).toContain("<time>2026-01-15</time>");
    expect(post).toContain("<li>intro</li><li>typescript</li>");
  });

  it("highlights code blocks in built pages", async () => {
    const post = await readOut(fixture, "posts/hello/index.html");
    expect(post).toContain('class="hljs language-ts"');
    expect(post).toContain("hljs-");
  });

  it("excludes drafts by default", async () => {
    expect(await exists(fixture, "posts/secret/index.html")).toBe(false);
  });

  it("generates tag index pages listing tagged posts", async () => {
    const intro = await readOut(fixture, "tags/intro/index.html");
    expect(intro).toContain("Posts tagged intro");
    expect(intro).toContain('<a href="/posts/hello/">Hello World</a>');
    expect(intro).toContain('<a href="/posts/second/">Second Post</a>');

    const ts = await readOut(fixture, "tags/typescript/index.html");
    expect(ts).toContain("Hello World");
    expect(ts).not.toContain("Second Post");
  });

  it("generates an all-tags overview with counts", async () => {
    const tags = await readOut(fixture, "tags/index.html");
    expect(tags).toContain('<a href="/tags/intro/">intro (2)</a>');
    expect(tags).toContain('<a href="/tags/news/">news (1)</a>');
  });

  it("generates a valid RSS feed without drafts", async () => {
    const feed = await readOut(fixture, "feed.xml");
    expect(feed).toContain('<rss version="2.0"');
    expect(feed).toContain("<title>Test Site</title>");
    expect(feed).toContain("<link>https://example.com/posts/hello/</link>");
    expect(feed).toContain("<title>Hello World</title>");
    expect(feed).not.toContain("Secret");
    // Newest first
    expect(feed.indexOf("Second Post")).toBeLessThan(feed.indexOf("Hello World"));
  });

  it("copies non-markdown files through unchanged", async () => {
    expect(await readOut(fixture, "style.css")).toContain("font-family: sans-serif");
  });

  it("includes drafts when includeDrafts is set", async () => {
    const withDrafts = await makeFixture();
    try {
      const result = await buildSite({
        sourceDir: withDrafts.sourceDir,
        templateDir: withDrafts.templateDir,
        outDir: withDrafts.outDir,
        includeDrafts: true,
      });
      expect(result.skippedDrafts).toBe(0);
      expect(await exists(withDrafts, "posts/secret/index.html")).toBe(true);
    } finally {
      await withDrafts.cleanup();
    }
  });

  it("reports skipped drafts and sorted pages in the result", async () => {
    const second = await makeFixture();
    try {
      const result = await buildSite({
        sourceDir: second.sourceDir,
        templateDir: second.templateDir,
        outDir: second.outDir,
      });
      expect(result.skippedDrafts).toBe(1);
      expect(result.pages.map((p) => p.meta.title)).toEqual([
        "Second Post",
        "Hello World",
        "Home",
      ]);
      expect(result.tagPages.sort()).toEqual(["/tags/intro/", "/tags/news/", "/tags/typescript/"]);
    } finally {
      await second.cleanup();
    }
  });
});
