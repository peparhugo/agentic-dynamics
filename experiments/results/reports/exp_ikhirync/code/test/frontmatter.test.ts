import { describe, it, expect } from "vitest";
import { parseFrontmatter } from "../src/frontmatter.js";

describe("parseFrontmatter", () => {
  it("extracts title, date, and tags", () => {
    const input = `---
title: My Post
date: 2025-06-01
tags:
  - js
  - web
---
Some content.`;

    const { frontmatter, content } = parseFrontmatter(input);
    expect(frontmatter.title).toBe("My Post");
    expect(frontmatter.date).toBe("2025-06-01");
    expect(frontmatter.tags).toEqual(["js", "web"]);
    expect(content).toBe("Some content.");
  });

  it("defaults draft to false when absent", () => {
    const input = `---
title: No Draft
---
Content`;

    const { frontmatter } = parseFrontmatter(input);
    expect(frontmatter.draft).toBe(false);
  });

  it("reads draft: true", () => {
    const input = `---
title: Secret
draft: true
---
Hidden`;

    const { frontmatter } = parseFrontmatter(input);
    expect(frontmatter.draft).toBe(true);
  });

  it("normalizes a string tag into an array", () => {
    const input = `---
title: OneTag
tags: solo
---
Body`;

    const { frontmatter } = parseFrontmatter(input);
    expect(frontmatter.tags).toEqual(["solo"]);
  });

  it("handles empty frontmatter", () => {
    const input = `No frontmatter here.`;
    const { frontmatter, content } = parseFrontmatter(input);
    expect(frontmatter.draft).toBe(false);
    expect(content).toBe("No frontmatter here.");
  });

  it("trims surrounding whitespace from content", () => {
    const input = `---
title: Trim
---

  padded content  

`;
    const { content } = parseFrontmatter(input);
    expect(content).toBe("padded content");
  });

  it("preserves arbitrary extra frontmatter keys", () => {
    const input = `---
title: Extra
author: Alice
custom: 42
---
.`;

    const { frontmatter } = parseFrontmatter(input);
    expect(frontmatter.author).toBe("Alice");
    expect(frontmatter.custom).toBe(42);
  });
});
