import { describe, it, expect } from "vitest";
import { parseFrontmatter } from "../src/frontmatter.js";

describe("parseFrontmatter", () => {
  it("parses title, date, tags, draft", () => {
    const { frontmatter, body } = parseFrontmatter(
      `---
title: Hello World
date: 2024-03-15
tags: [ts, node]
draft: true
---
Body text.`
    );
    expect(frontmatter.title).toBe("Hello World");
    expect(frontmatter.date).toBeInstanceOf(Date);
    expect(frontmatter.date!.toISOString().slice(0, 10)).toBe("2024-03-15");
    expect(frontmatter.tags).toEqual(["ts", "node"]);
    expect(frontmatter.draft).toBe(true);
    expect(body.trim()).toBe("Body text.");
  });

  it("handles missing frontmatter with defaults", () => {
    const { frontmatter, body } = parseFrontmatter("Just markdown.", "fallback");
    expect(frontmatter.title).toBe("fallback");
    expect(frontmatter.date).toBeNull();
    expect(frontmatter.tags).toEqual([]);
    expect(frontmatter.draft).toBe(false);
    expect(body).toBe("Just markdown.");
  });

  it("parses comma-separated tag strings", () => {
    const { frontmatter } = parseFrontmatter(`---\ntags: a, b , c\n---\nx`);
    expect(frontmatter.tags).toEqual(["a", "b", "c"]);
  });

  it("coerces draft strings and rejects invalid dates", () => {
    const { frontmatter } = parseFrontmatter(`---\ndraft: "true"\ndate: not-a-date\n---\nx`);
    expect(frontmatter.draft).toBe(true);
    expect(frontmatter.date).toBeNull();
  });

  it("passes through custom fields and layout", () => {
    const { frontmatter } = parseFrontmatter(`---\nlayout: wide\nauthor: Ada\n---\nx`);
    expect(frontmatter.layout).toBe("wide");
    expect(frontmatter.author).toBe("Ada");
  });

  it("trims whitespace-only titles to fallback", () => {
    const { frontmatter } = parseFrontmatter(`---\ntitle: "   "\n---\nx`, "fb");
    expect(frontmatter.title).toBe("fb");
  });
});
