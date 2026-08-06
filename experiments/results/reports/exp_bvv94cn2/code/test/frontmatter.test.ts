import { describe, it, expect } from "vitest";
import { parseFrontmatter } from "../src/frontmatter.js";

describe("parseFrontmatter", () => {
  it("parses YAML frontmatter between --- delimiters", () => {
    const input = `---
title: Test Post
date: 2024-01-15
tags:
  - js
  - css
draft: false
---
# Hello

Content here.`;

    const result = parseFrontmatter(input);
    expect(result.frontmatter.title).toBe("Test Post");
    expect(result.frontmatter.date).toBe("2024-01-15");
    expect(result.frontmatter.tags).toEqual(["js", "css"]);
    expect(result.frontmatter.draft).toBe(false);
    expect(result.body).toContain("# Hello");
    expect(result.body).toContain("Content here.");
  });

  it("returns default title when no frontmatter", () => {
    const input = "# Just markdown\n\nNo frontmatter here.";
    const result = parseFrontmatter(input);
    expect(result.frontmatter.title).toBe("Untitled");
    expect(result.body).toBe(input);
  });

  it("handles missing closing delimiter gracefully", () => {
    const input = `---
title: Incomplete
# Content`;

    const result = parseFrontmatter(input);
    expect(result.frontmatter.title).toBe("Untitled");
  });

  it("normalizes tags to lowercase trimmed strings", () => {
    const input = `---
title: Tag Test
tags:
  -  JavaScript
  - "  TypeScript  "
  - CSS
---
Body`;

    const result = parseFrontmatter(input);
    expect(result.frontmatter.tags).toEqual(["javascript", "typescript", "css"]);
  });

  it("handles non-array tags by wrapping in array", () => {
    const input = `---
title: Single Tag
tags: javascript
---
Body`;

    const result = parseFrontmatter(input);
    expect(result.frontmatter.tags).toEqual(["javascript"]);
  });

  it("sets default title when title is missing in frontmatter", () => {
    const input = `---
date: 2024-01-01
---
Body`;

    const result = parseFrontmatter(input);
    expect(result.frontmatter.title).toBe("Untitled");
    expect(result.frontmatter.date).toBe("2024-01-01");
  });

  it("handles empty frontmatter block", () => {
    const input = `---
---
Body`;

    const result = parseFrontmatter(input);
    expect(result.frontmatter.title).toBe("Untitled");
    expect(result.body).toBe("Body");
  });

  it("handles empty body after frontmatter", () => {
    const input = `---
title: Only Meta
---`;

    const result = parseFrontmatter(input);
    expect(result.frontmatter.title).toBe("Only Meta");
    expect(result.body).toBe("");
  });

  it("handles malformed YAML gracefully", () => {
    const input = `---
title: Broken
{{{invalid
---
Body`;

    const result = parseFrontmatter(input);
    expect(result.frontmatter.title).toBe("Untitled");
    expect(result.body).toBe("Body");
  });

  it("handles empty object YAML", () => {
    const input = `---
{}
---
Body`;

    const result = parseFrontmatter(input);
    expect(result.frontmatter.title).toBe("Untitled");
  });

  it("preserves body content exactly", () => {
    const input = `---
title: Preserve
---
Line 1
Line 2

Line 3`;

    const result = parseFrontmatter(input);
    expect(result.body).toBe("Line 1\nLine 2\n\nLine 3");
  });
});
