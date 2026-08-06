import { describe, it, expect } from "vitest";
import { parseFrontmatter } from "../src/frontmatter.js";

describe("parseFrontmatter", () => {
  it("parses title, date, tags, and draft from YAML frontmatter", () => {
    const raw = `---
title: Test Post
date: 2024-01-15
tags: [js, ts]
draft: false
---
Content here.`;

    const { frontmatter, content } = parseFrontmatter(raw);
    expect(frontmatter.title).toBe("Test Post");
    expect(frontmatter.date).toBeInstanceOf(Date);
    expect((frontmatter.date as Date).getFullYear()).toBe(2024);
    expect(frontmatter.tags).toEqual(["js", "ts"]);
    expect(frontmatter.draft).toBe(false);
    expect(content.trim()).toBe("Content here.");
  });

  it("treats comma-separated tag string as array", () => {
    const raw = `---
title: T
tags: a, b, c
---
body`;

    const { frontmatter } = parseFrontmatter(raw);
    expect(frontmatter.tags).toEqual(["a", "b", "c"]);
  });

  it("defaults tags to empty array and draft to false", () => {
    const raw = `---
title: No tags
---
body`;

    const { frontmatter } = parseFrontmatter(raw);
    expect(frontmatter.tags).toEqual([]);
    expect(frontmatter.draft).toBe(false);
  });

  it("converts string date to Date object", () => {
    const raw = `---
title: Dated
date: "2024-06-01"
---
body`;

    const { frontmatter } = parseFrontmatter(raw);
    expect(frontmatter.date).toBeInstanceOf(Date);
  });

  it("handles draft: true string", () => {
    const raw = `---
title: Drafted
draft: "true"
---
content`;

    const { frontmatter } = parseFrontmatter(raw);
    expect(frontmatter.draft).toBe(true);
  });

  it("handles missing frontmatter gracefully", () => {
    const raw = `Just raw content, no frontmatter.`;
    const { frontmatter, content } = parseFrontmatter(raw);
    expect(frontmatter.title).toBeUndefined();
    expect(content.trim()).toBe("Just raw content, no frontmatter.");
    expect(frontmatter.tags).toEqual([]);
  });
});
