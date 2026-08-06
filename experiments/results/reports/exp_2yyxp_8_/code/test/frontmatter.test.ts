import { describe, it, expect } from "vitest";
import { parseFrontmatter, isPublished, pageUrl, sortByDate } from "../src/frontmatter";
import { Page } from "../src/types";

describe("parseFrontmatter", () => {
  it("parses title from YAML frontmatter", () => {
    const raw = `---
title: Test Post
---
Content here.`;

    const { frontmatter, content } = parseFrontmatter(raw, "test.md");
    expect(frontmatter.title).toBe("Test Post");
    expect(content.trim()).toBe("Content here.");
  });

  it("parses date as Date object", () => {
    const raw = `---
title: Post
date: 2025-06-15
---
Content`;

    const { frontmatter } = parseFrontmatter(raw, "post.md");
    expect(frontmatter.date).toBeInstanceOf(Date);
    expect(frontmatter.date!.getFullYear()).toBe(2025);
    expect(frontmatter.date!.getMonth()).toBe(5);
    expect(frontmatter.date!.getDate()).toBe(15);
  });

  it("parses tags array", () => {
    const raw = `---
title: Post
tags:
  - js
  - ts
  - rust
---
Content`;

    const { frontmatter } = parseFrontmatter(raw, "post.md");
    expect(frontmatter.tags).toEqual(["js", "ts", "rust"]);
  });

  it("parses comma-separated tags string", () => {
    const raw = `---
title: Post
tags: js, ts, rust
---
Content`;

    const { frontmatter } = parseFrontmatter(raw, "post.md");
    expect(frontmatter.tags).toEqual(["js", "ts", "rust"]);
  });

  it("parses draft flag", () => {
    const raw = `---
title: Draft
draft: true
---
Content`;

    const { frontmatter } = parseFrontmatter(raw, "draft.md");
    expect(frontmatter.draft).toBe(true);
  });

  it("defaults draft to falsy when not set", () => {
    const raw = `---
title: Post
---
Content`;

    const { frontmatter } = parseFrontmatter(raw, "post.md");
    expect(frontmatter.draft).toBeFalsy();
  });

  it("defaults tags to empty array", () => {
    const raw = `---
title: Post
---
Content`;

    const { frontmatter } = parseFrontmatter(raw, "post.md");
    expect(frontmatter.tags).toEqual([]);
  });

  it("handles missing all optional fields", () => {
    const raw = "# Just markdown\n\nNo frontmatter at all.";

    const { frontmatter, content } = parseFrontmatter(raw, "plain.md");
    expect(frontmatter.title).toBeUndefined();
    expect(frontmatter.date).toBeUndefined();
    expect(frontmatter.tags).toEqual([]);
    expect(frontmatter.draft).toBeFalsy();
    expect(content).toContain("Just markdown");
  });

  it("handles custom frontmatter fields", () => {
    const raw = `---
title: Post
layout: custom
author: Alice
---
Content`;

    const { frontmatter } = parseFrontmatter(raw, "post.md");
    expect(frontmatter["layout"]).toBe("custom");
    expect(frontmatter["author"]).toBe("Alice");
  });
});

describe("isPublished", () => {
  it("returns true for non-draft", () => {
    expect(isPublished({ draft: false })).toBe(true);
    expect(isPublished({})).toBe(true);
  });

  it("returns false for drafts", () => {
    expect(isPublished({ draft: true })).toBe(false);
  });
});

describe("pageUrl", () => {
  it("converts .md to .html", () => {
    expect(pageUrl("hello.md")).toBe("/hello.html");
  });

  it("handles nested paths", () => {
    expect(pageUrl("posts/hello.md")).toBe("/posts/hello.html");
  });

  it("preserves leading slash", () => {
    expect(pageUrl("/posts/hello.md")).toBe("/posts/hello.html");
  });

  it("converts index.md to directory path", () => {
    expect(pageUrl("posts/index.md")).toBe("/posts/");
  });

  it("does not convert root index.md", () => {
    const result = pageUrl("index.md");
    expect(result).toBe("/index.html");
  });
});

describe("sortByDate", () => {
  it("sorts newest first", () => {
    const pages: Page[] = [
      {
        path: "a.md", url: "/a.html",
        frontmatter: { title: "A", date: new Date("2025-01-01") },
        content: "", html: "", raw: "",
      },
      {
        path: "b.md", url: "/b.html",
        frontmatter: { title: "B", date: new Date("2025-06-01") },
        content: "", html: "", raw: "",
      },
      {
        path: "c.md", url: "/c.html",
        frontmatter: { title: "C", date: new Date("2024-12-01") },
        content: "", html: "", raw: "",
      },
    ];

    const sorted = [...pages].sort(sortByDate);
    expect(sorted[0].frontmatter.title).toBe("B");
    expect(sorted[1].frontmatter.title).toBe("A");
    expect(sorted[2].frontmatter.title).toBe("C");
  });

  it("puts undated entries last", () => {
    const pages: Page[] = [
      { path: "a.md", url: "/a.html", frontmatter: { title: "A", date: new Date("2025-01-01") }, content: "", html: "", raw: "" },
      { path: "b.md", url: "/b.html", frontmatter: { title: "B" }, content: "", html: "", raw: "" },
    ];

    const sorted = [...pages].sort(sortByDate);
    expect(sorted[0].frontmatter.title).toBe("A");
    expect(sorted[1].frontmatter.title).toBe("B");
  });
});
