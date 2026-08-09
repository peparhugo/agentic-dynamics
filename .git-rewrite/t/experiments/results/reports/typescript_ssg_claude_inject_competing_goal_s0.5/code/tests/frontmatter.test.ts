import { describe, it, expect } from "vitest";
import { parseDocument } from "../src/frontmatter.js";

describe("parseDocument", () => {
  it("parses title, date, tags, and draft", () => {
    const { frontmatter, body } = parseDocument(
      `---
title: Hello World
date: 2024-03-01
tags: [alpha, beta]
draft: true
---
# Heading
`
    );
    expect(frontmatter.title).toBe("Hello World");
    expect(frontmatter.date).toBeInstanceOf(Date);
    expect(frontmatter.date!.toISOString().slice(0, 10)).toBe("2024-03-01");
    expect(frontmatter.tags).toEqual(["alpha", "beta"]);
    expect(frontmatter.draft).toBe(true);
    expect(body.trim()).toBe("# Heading");
  });

  it("handles missing frontmatter with defaults", () => {
    const { frontmatter, body } = parseDocument("just text", "my-file");
    expect(frontmatter.title).toBe("my-file");
    expect(frontmatter.date).toBeNull();
    expect(frontmatter.tags).toEqual([]);
    expect(frontmatter.draft).toBe(false);
    expect(frontmatter.layout).toBe("default");
    expect(body).toBe("just text");
  });

  it("accepts comma-separated tag strings", () => {
    const { frontmatter } = parseDocument(`---\ntags: a, b , c\n---\nx`);
    expect(frontmatter.tags).toEqual(["a", "b", "c"]);
  });

  it("treats non-boolean draft values as not draft", () => {
    const { frontmatter } = parseDocument(`---\ndraft: "yes"\n---\nx`);
    expect(frontmatter.draft).toBe(false);
  });

  it("normalizes invalid dates to null", () => {
    const { frontmatter } = parseDocument(`---\ndate: not-a-date\n---\nx`);
    expect(frontmatter.date).toBeNull();
  });

  it("preserves custom frontmatter keys", () => {
    const { frontmatter } = parseDocument(`---\nauthor: Ada\nlayout: post\n---\nx`);
    expect(frontmatter.author).toBe("Ada");
    expect(frontmatter.layout).toBe("post");
  });
});
