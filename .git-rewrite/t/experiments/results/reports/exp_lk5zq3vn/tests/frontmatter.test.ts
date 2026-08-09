import { describe, it, expect } from "vitest";
import { parseFrontmatter } from "../src/frontmatter.js";

describe("parseFrontmatter", () => {
  it("parses title, date, tags, draft", () => {
    const { frontmatter, body } = parseFrontmatter(
      `---
title: Hello World
date: 2026-01-15
tags: [ts, web]
draft: true
---
# Body here
`
    );
    expect(frontmatter.title).toBe("Hello World");
    expect(frontmatter.date?.toISOString().slice(0, 10)).toBe("2026-01-15");
    expect(frontmatter.tags).toEqual(["ts", "web"]);
    expect(frontmatter.draft).toBe(true);
    expect(body.trim()).toBe("# Body here");
  });

  it("handles missing frontmatter with sane defaults", () => {
    const { frontmatter, body } = parseFrontmatter("just markdown");
    expect(frontmatter).toMatchObject({ title: "", date: null, tags: [], draft: false, layout: "default" });
    expect(body).toBe("just markdown");
  });

  it("coerces comma-separated tag strings", () => {
    const { frontmatter } = parseFrontmatter(`---\ntags: a, b , c\n---\nx`);
    expect(frontmatter.tags).toEqual(["a", "b", "c"]);
  });

  it("coerces draft strings and defaults to false", () => {
    expect(parseFrontmatter(`---\ndraft: "true"\n---\nx`).frontmatter.draft).toBe(true);
    expect(parseFrontmatter(`---\ndraft: "nope"\n---\nx`).frontmatter.draft).toBe(false);
    expect(parseFrontmatter(`---\ntitle: t\n---\nx`).frontmatter.draft).toBe(false);
  });

  it("returns null for invalid dates", () => {
    expect(parseFrontmatter(`---\ndate: not-a-date\n---\nx`).frontmatter.date).toBeNull();
  });

  it("passes unknown keys through extra", () => {
    const { frontmatter } = parseFrontmatter(`---\ntitle: t\nauthor: Ada\n---\nx`);
    expect(frontmatter.extra).toEqual({ author: "Ada" });
  });

  it("respects custom layout", () => {
    const { frontmatter } = parseFrontmatter(`---\nlayout: post\n---\nx`);
    expect(frontmatter.layout).toBe("post");
  });
});
