import { describe, it, expect } from "vitest";
import { parseFrontmatter, titleFromSlug } from "../src/frontmatter.js";

describe("parseFrontmatter", () => {
  it("parses title, date, tags, and draft", () => {
    const { meta, body } = parseFrontmatter(`---
title: My Post
date: 2026-01-15
tags: [a, b]
draft: true
---
Body text.
`);
    expect(meta.title).toBe("My Post");
    expect(meta.date).toEqual(new Date("2026-01-15"));
    expect(meta.tags).toEqual(["a", "b"]);
    expect(meta.draft).toBe(true);
    expect(body.trim()).toBe("Body text.");
  });

  it("applies defaults when frontmatter is missing", () => {
    const { meta, body } = parseFrontmatter("Just markdown.", "Fallback");
    expect(meta.title).toBe("Fallback");
    expect(meta.date).toBeNull();
    expect(meta.tags).toEqual([]);
    expect(meta.draft).toBe(false);
    expect(meta.layout).toBe("default");
    expect(body).toBe("Just markdown.");
  });

  it("normalizes comma-separated tag strings", () => {
    const { meta } = parseFrontmatter(`---
tags: one, two , three
---
x`);
    expect(meta.tags).toEqual(["one", "two", "three"]);
  });

  it("de-duplicates and trims tags", () => {
    const { meta } = parseFrontmatter(`---
tags: [" a", a, "b "]
---
x`);
    expect(meta.tags).toEqual(["a", "b"]);
  });

  it("parses date strings and rejects invalid dates", () => {
    const ok = parseFrontmatter(`---\ndate: "2026-02-01T10:00:00Z"\n---\nx`);
    expect(ok.meta.date?.toISOString()).toBe("2026-02-01T10:00:00.000Z");

    const bad = parseFrontmatter(`---\ndate: "not a date"\n---\nx`);
    expect(bad.meta.date).toBeNull();
  });

  it('treats draft: "true" (string) as a draft', () => {
    const { meta } = parseFrontmatter(`---\ndraft: "true"\n---\nx`);
    expect(meta.draft).toBe(true);
  });

  it("keeps unknown keys in extra", () => {
    const { meta } = parseFrontmatter(`---\ntitle: T\nauthor: Ada\n---\nx`);
    expect(meta.extra).toEqual({ author: "Ada" });
  });

  it("uses custom layout when specified", () => {
    const { meta } = parseFrontmatter(`---\nlayout: post\n---\nx`);
    expect(meta.layout).toBe("post");
  });
});

describe("titleFromSlug", () => {
  it("title-cases the final slug segment", () => {
    expect(titleFromSlug("posts/hello-world")).toBe("Hello World");
    expect(titleFromSlug("my_page")).toBe("My Page");
  });
});
