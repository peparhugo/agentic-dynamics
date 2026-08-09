import { describe, it, expect, beforeEach } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { buildSite, buildTagIndex, loadPosts, slugify } from "../src/build.js";
import type { SiteConfig } from "../src/types.js";
import { makeTmpDir, writeTree, BASIC_TEMPLATES } from "./helpers.js";

function makeSite(overrides: Partial<SiteConfig> = {}): SiteConfig {
  const root = makeTmpDir();
  const site: SiteConfig = {
    sourceDir: path.join(root, "content"),
    templateDir: path.join(root, "templates"),
    outDir: path.join(root, "out"),
    baseUrl: "https://example.com",
    title: "Test Site",
    includeDrafts: false,
    ...overrides,
  };
  writeTree(site.templateDir, BASIC_TEMPLATES);
  writeTree(site.sourceDir, {
    "hello.md": `---\ntitle: Hello\ndate: 2024-01-02\ntags: [news, misc]\n---\n# Hello\n\nFirst post.`,
    "posts/second.md": `---\ntitle: Second\ndate: 2024-02-03\ntags: [news]\n---\nSecond post with code:\n\n\`\`\`js\nconst x = 1;\n\`\`\`\n`,
    "secret.md": `---\ntitle: Secret\ndraft: true\n---\nHidden.`,
    "style.css": "body { color: red; }",
  });
  return site;
}

describe("slugify", () => {
  it("lowercases and dashes non-alphanumerics", () => {
    expect(slugify("Hello World!")).toBe("hello-world");
    expect(slugify("  --A_B--  ")).toBe("a-b");
  });
});

describe("loadPosts", () => {
  it("skips drafts by default and sorts newest first", () => {
    const site = makeSite();
    const posts = loadPosts(site);
    expect(posts.map((p) => p.frontmatter.title)).toEqual(["Second", "Hello"]);
  });

  it("includes drafts when includeDrafts is set", () => {
    const site = makeSite({ includeDrafts: true });
    const posts = loadPosts({ ...site, includeDrafts: true });
    expect(posts.map((p) => p.frontmatter.title)).toContain("Secret");
  });

  it("derives nested slugs and URLs from file paths", () => {
    const site = makeSite();
    const second = loadPosts(site).find((p) => p.frontmatter.title === "Second")!;
    expect(second.slug).toBe("posts/second");
    expect(second.url).toBe("/posts/second/");
  });
});

describe("buildTagIndex", () => {
  it("groups posts by slugified tag", () => {
    const site = makeSite();
    const index = buildTagIndex(loadPosts(site));
    expect([...index.keys()].sort()).toEqual(["misc", "news"]);
    expect(index.get("news")!.length).toBe(2);
    expect(index.get("misc")!.length).toBe(1);
  });
});

describe("buildSite", () => {
  let site: SiteConfig;
  beforeEach(() => {
    site = makeSite();
  });

  const read = (rel: string) => fs.readFileSync(path.join(site.outDir, rel), "utf8");

  it("writes post pages wrapped in the layout", () => {
    buildSite(site);
    const html = read("hello/index.html");
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("<title>Hello</title>");
    expect(html).toContain("First post.");
    expect(html).toContain("<header>Test Site</header>");
  });

  it("applies syntax highlighting in built pages", () => {
    buildSite(site);
    expect(read("posts/second/index.html")).toContain("hljs-keyword");
  });

  it("writes an index page listing all posts", () => {
    buildSite(site);
    const html = read("index.html");
    expect(html).toContain('href="/hello/"');
    expect(html).toContain('href="/posts/second/"');
    expect(html).not.toContain("Secret");
  });

  it("writes tag index pages", () => {
    buildSite(site);
    const news = read("tags/news/index.html");
    expect(news).toContain("Tag: news");
    expect(news).toContain("Hello");
    expect(news).toContain("Second");
    const misc = read("tags/misc/index.html");
    expect(misc).not.toContain("Second");
  });

  it("links tag pages from the index", () => {
    buildSite(site);
    expect(read("index.html")).toContain('href="/tags/news/"');
    expect(read("index.html")).toContain("news (2)");
  });

  it("generates a valid RSS feed with absolute links, dates, categories", () => {
    buildSite(site);
    const rss = read("rss.xml");
    expect(rss).toContain('<rss version="2.0">');
    expect(rss).toContain("<title>Test Site</title>");
    expect(rss).toContain("<link>https://example.com/hello/</link>");
    expect(rss).toContain("<category>news</category>");
    expect(rss).toMatch(/<pubDate>[A-Z][a-z]{2}, \d{2} [A-Z][a-z]{2} \d{4}/);
    expect(rss).not.toContain("Secret");
  });

  it("escapes XML entities in RSS", () => {
    writeTree(site.sourceDir, {
      "amp.md": `---\ntitle: "Fish & <Chips>"\ndate: 2024-05-05\n---\nx`,
    });
    buildSite(site);
    expect(read("rss.xml")).toContain("<title>Fish &amp; &lt;Chips&gt;</title>");
  });

  it("copies static assets verbatim", () => {
    buildSite(site);
    expect(read("style.css")).toBe("body { color: red; }");
  });

  it("excludes drafts from output but includes them with includeDrafts", () => {
    buildSite(site);
    expect(fs.existsSync(path.join(site.outDir, "secret/index.html"))).toBe(false);
    buildSite({ ...site, includeDrafts: true });
    expect(fs.existsSync(path.join(site.outDir, "secret/index.html"))).toBe(true);
  });

  it("honors a per-post layout override", () => {
    writeTree(site.templateDir, { "layouts/bare.hbs": "<main>{{{body}}}</main>" });
    writeTree(site.sourceDir, {
      "bare-post.md": `---\ntitle: Bare\nlayout: bare\ndate: 2024-06-06\n---\nx`,
    });
    buildSite(site);
    const html = read("bare-post/index.html");
    expect(html).toContain("<main>");
    expect(html).not.toContain("<!DOCTYPE html>");
  });

  it("reports written pages in the result", () => {
    const result = buildSite(site);
    expect(result.posts.length).toBe(2);
    expect(result.pagesWritten).toContain("index.html");
    expect(result.pagesWritten).toContain("rss.xml");
    expect(result.pagesWritten.some((p) => p.includes("tags"))).toBe(true);
  });
});
