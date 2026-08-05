import { describe, it, expect } from "vitest";
import { parseFrontmatter } from "../src/frontmatter.js";

describe("parseFrontmatter", () => {
  it("parses title, date, tags, draft, layout", () => {
    const { data, content } = parseFrontmatter(
      `---
title: Hello World
date: 2024-03-15
tags: [ts, web]
draft: true
layout: post
---

Body here.`
    );
    expect(data.title).toBe("Hello World");
    expect(data.date?.toISOString().slice(0, 10)).toBe("2024-03-15");
    expect(data.tags).toEqual(["ts", "web"]);
    expect(data.draft).toBe(true);
    expect(data.layout).toBe("post");
    expect(content.trim()).toBe("Body here.");
  });

  it("applies defaults when frontmatter is absent", () => {
    const { data, content } = parseFrontmatter("Just markdown.");
    expect(data).toMatchObject({ title: "", date: null, tags: [], draft: false, layout: "default" });
    expect(content).toBe("Just markdown.");
  });

  it("applies defaults for missing keys in present frontmatter", () => {
    const { data } = parseFrontmatter("---\ntitle: Only Title\n---\nbody");
    expect(data.tags).toEqual([]);
    expect(data.draft).toBe(false);
    expect(data.date).toBeNull();
  });

  it("accepts comma-separated tags string", () => {
    const { data } = parseFrontmatter("---\ntags: a, b , c\n---\nx");
    expect(data.tags).toEqual(["a", "b", "c"]);
  });

  it("accepts YAML list tags", () => {
    const { data } = parseFrontmatter("---\ntags:\n  - alpha\n  - beta\n---\nx");
    expect(data.tags).toEqual(["alpha", "beta"]);
  });

  it("treats non-boolean draft values as false", () => {
    const { data } = parseFrontmatter('---\ndraft: "yes"\n---\nx');
    expect(data.draft).toBe(false);
  });

  it("ignores invalid dates", () => {
    const { data } = parseFrontmatter("---\ndate: not-a-date\n---\nx");
    expect(data.date).toBeNull();
  });

  it("preserves custom keys", () => {
    const { data } = parseFrontmatter("---\nauthor: Ada\n---\nx");
    expect(data.author).toBe("Ada");
  });

  it("handles CRLF line endings", () => {
    const { data, content } = parseFrontmatter("---\r\ntitle: CRLF\r\n---\r\nbody");
    expect(data.title).toBe("CRLF");
    expect(content).toBe("body");
  });

  it("does not treat a thematic break mid-document as frontmatter", () => {
    const { data, content } = parseFrontmatter("intro\n---\ntitle: nope\n---\n");
    expect(data.title).toBe("");
    expect(content.startsWith("intro")).toBe(true);
  });

  it("throws on non-mapping frontmatter", () => {
    expect(() => parseFrontmatter("---\n- just\n- a list\n---\nx")).toThrow(/mapping/);
  });
});
