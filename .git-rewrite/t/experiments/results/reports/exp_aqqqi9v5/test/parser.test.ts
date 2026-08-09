import { describe, it, expect } from "vitest";
import { parseFrontmatter } from "../src/parser.js";

describe("parseFrontmatter", () => {
  it("parses YAML frontmatter with title", () => {
    const input = `---
title: Hello World
---
Some content here.`;

    const { data, content } = parseFrontmatter(input);
    expect(data.title).toBe("Hello World");
    expect(content.trim()).toBe("Some content here.");
  });

  it("handles missing title gracefully", () => {
    const input = `---
date: 2024-01-01
---
Content.`;

    const { data } = parseFrontmatter(input);
    expect(data.title).toBe("Untitled");
    expect(data.date).toBe("2024-01-01");
  });

  it("parses tags as array", () => {
    const input = `---
title: Post
tags:
  - typescript
  - ssg
---
Body.`;

    const { data } = parseFrontmatter(input);
    expect(data.tags).toEqual(["typescript", "ssg"]);
  });

  it("parses tags as comma-separated string", () => {
    const input = `---
title: Post
tags: js, ts, css
---
Body.`;

    const { data } = parseFrontmatter(input);
    expect(data.tags).toEqual(["js", "ts", "css"]);
  });

  it("parses draft boolean", () => {
    const input = `---
title: Draft Post
draft: true
---
Hidden.`;

    const { data } = parseFrontmatter(input);
    expect(data.draft).toBe(true);
  });

  it("draft defaults to false when omitted", () => {
    const input = `---
title: Published
---
Visible.`;

    const { data } = parseFrontmatter(input);
    expect(data.draft).toBeUndefined();
  });

  it("preserves extra frontmatter fields", () => {
    const input = `---
title: Extra
author: Alice
rating: 5
---
Extra content.`;

    const { data } = parseFrontmatter(input);
    expect(data.author).toBe("Alice");
    expect(data.rating).toBe(5);
  });

  it("parses date as string", () => {
    const input = `---
title: Dated
date: 2025-06-15
---
Content.`;

    const { data } = parseFrontmatter(input);
    expect(data.date).toBe("2025-06-15");
  });

  it("handles empty frontmatter", () => {
    const input = `---
---
Just content with no metadata.`;

    const { data, content } = parseFrontmatter(input);
    expect(data.title).toBe("Untitled");
    expect(content.trim()).toBe("Just content with no metadata.");
  });

  it("handles content with no frontmatter", () => {
    const input = "Plain markdown without frontmatter.";
    const { data, content } = parseFrontmatter(input);
    expect(data.title).toBe("Untitled");
    expect(content).toBe("Plain markdown without frontmatter.");
  });
});
