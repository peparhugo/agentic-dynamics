import { describe, it, expect } from "vitest";
import { generateRssXml } from "../src/rss";
import { Post } from "../src/types";

describe("generateRssXml", () => {
  it("generates valid RSS XML", () => {
    const posts: Post[] = [
      {
        title: "Test Post",
        date: "2024-01-01",
        slug: "test-post",
        tags: [],
        content: "Body",
        draft: false,
        excerpt: "An excerpt.",
      },
    ];

    const xml = generateRssXml(
      { title: "My Blog", description: "A blog", url: "https://example.com", author: "Me" },
      posts
    );

    expect(xml).toContain('<?xml version="1.0" encoding="utf-8"?>');
    expect(xml).toContain("<rss version=\"2.0\"");
    expect(xml).toContain("<title>My Blog</title>");
    expect(xml).toContain("<title>Test Post</title>");
    expect(xml).toContain("<link>https://example.com/test-post.html</link>");
    expect(xml).toContain("<description>An excerpt.</description>");
    expect(xml).toContain('<guid>https://example.com/test-post.html</guid>');
  });

  it("escapes XML special characters", () => {
    const posts: Post[] = [
      {
        title: "Foo & Bar",
        date: "2024-01-01",
        slug: "foo-bar",
        tags: [],
        content: "",
        draft: false,
        excerpt: "Test <b>bold</b>",
      },
    ];

    const xml = generateRssXml(
      { title: "A & B", description: "", url: "", author: "" },
      posts
    );

    expect(xml).toContain("&amp;");
    expect(xml).toContain("&lt;b&gt;");
  });

  it("handles empty posts array", () => {
    const xml = generateRssXml(
      { title: "Empty", description: "", url: "", author: "" },
      []
    );

    expect(xml).toContain("<rss");
    expect(xml).not.toContain("<item>");
  });
});
