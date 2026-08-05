import { describe, it, expect } from "vitest";
import { generateRssFeed } from "../src/lib/rss";
import { BuildContext, Post } from "../src/lib/types";
import { initMarked } from "../src/lib/markdown";

function makeCtx(posts: Post[]): BuildContext {
  return {
    posts,
    tags: [],
    config: {
      title: "Test Blog",
      description: "A test blog",
      url: "https://example.com",
      language: "en",
    },
    sourceDir: "/src",
    templateDir: "/tpl",
    outputDir: "/out",
  };
}

describe("generateRssFeed", () => {
  beforeAll(() => {
    initMarked();
  });

  it("generates valid XML for a single post", () => {
    const post: Post = {
      slug: "hello",
      sourcePath: "/src/hello.md",
      frontmatter: { title: "Hello World", date: "2024-06-01", tags: ["misc"] },
      body: "Hello",
      html: "<p>Hello</p>",
      url: "/hello.html",
    };

    const xml = generateRssFeed(makeCtx([post]));
    expect(xml).toContain("<rss");
    expect(xml).toContain("<title>Hello World</title>");
    expect(xml).toContain("<link>https://example.com/hello.html</link>");
    expect(xml).toContain("<description><![CDATA[<p>Hello</p>]]></description>");
  });

  it("excludes draft posts", () => {
    const published: Post = {
      slug: "pub",
      sourcePath: "/src/pub.md",
      frontmatter: { title: "Published", date: "2024-01-01" },
      body: "pub",
      html: "<p>pub</p>",
      url: "/pub.html",
    };

    const draft: Post = {
      slug: "draft",
      sourcePath: "/src/draft.md",
      frontmatter: { title: "Draft", date: "2024-01-01", draft: true },
      body: "draft",
      html: "<p>draft</p>",
      url: "/draft.html",
    };

    const xml = generateRssFeed(makeCtx([published, draft]));
    expect(xml).toContain("Published");
    expect(xml).not.toContain("Draft");
  });

  it("includes channel metadata", () => {
    const xml = generateRssFeed(makeCtx([]));
    expect(xml).toContain("<title>Test Blog</title>");
    expect(xml).toContain("<description>A test blog</description>");
    expect(xml).toContain("<link>https://example.com</link>");
    expect(xml).toContain("<language>en</language>");
  });

  it("sorts posts by date descending", () => {
    const older: Post = {
      slug: "older",
      sourcePath: "/src/older.md",
      frontmatter: { title: "Older", date: "2024-01-01" },
      body: "older",
      html: "<p>older</p>",
      url: "/older.html",
    };

    const newer: Post = {
      slug: "newer",
      sourcePath: "/src/newer.md",
      frontmatter: { title: "Newer", date: "2024-06-01" },
      body: "newer",
      html: "<p>newer</p>",
      url: "/newer.html",
    };

    const xml = generateRssFeed(makeCtx([older, newer]));
    const newerIdx = xml.indexOf("Newer");
    const olderIdx = xml.indexOf("Older");
    expect(newerIdx).toBeLessThan(olderIdx);
  });

  it("includes categories/tags in feed items", () => {
    const post: Post = {
      slug: "tagged",
      sourcePath: "/src/tagged.md",
      frontmatter: { title: "Tagged Post", date: "2024-01-01", tags: ["ts", "node"] },
      body: "tagged",
      html: "<p>tagged</p>",
      url: "/tagged.html",
    };

    const xml = generateRssFeed(makeCtx([post]));
    expect(xml).toContain("<category>ts</category>");
    expect(xml).toContain("<category>node</category>");
  });
});
