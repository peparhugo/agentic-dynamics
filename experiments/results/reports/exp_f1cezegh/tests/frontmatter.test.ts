import { describe, it, expect } from "vitest";
import { parseFrontmatter } from "../src/frontmatter";
import { PageMeta } from "../src/types";

describe("parseFrontmatter", () => {
  it("parses title from YAML frontmatter", () => {
    const input = `---
title: Hello World
date: 2024-01-15
---
Content here.`;

    const { meta, content } = parseFrontmatter(input);
    expect(meta.title).toBe("Hello World");
    expect(meta.date).toBeInstanceOf(Date);
    expect(meta.date!.getFullYear()).toBe(2024);
    expect(content.trim()).toBe("Content here.");
  });

  it("defaults title to Untitled when missing", () => {
    const input = `---
date: 2024-01-15
---
Content.`;

    const { meta } = parseFrontmatter(input);
    expect(meta.title).toBe("Untitled");
  });

  it("parses tags as array", () => {
    const input = `---
title: Post
tags:
  - typescript
  - javascript
  - node
---
Content.`;

    const { meta } = parseFrontmatter(input);
    expect(meta.tags).toEqual(["typescript", "javascript", "node"]);
  });

  it("parses tags as comma-separated string", () => {
    const input = `---
title: Post
tags: typescript, javascript, node
---
Content.`;

    const { meta } = parseFrontmatter(input);
    expect(meta.tags).toEqual(["typescript", "javascript", "node"]);
  });

  it("handles empty tags", () => {
    const input = `---
title: Post
---
Content.`;

    const { meta } = parseFrontmatter(input);
    expect(meta.tags).toEqual([]);
  });

  it("parses draft boolean", () => {
    const draftInput = `---
title: Draft Post
draft: true
---
Hidden content.`;

    const publishedInput = `---
title: Published
draft: false
---
Visible content.`;

    const noDraftInput = `---
title: Default
---
Content.`;

    expect(parseFrontmatter(draftInput).meta.draft).toBe(true);
    expect(parseFrontmatter(publishedInput).meta.draft).toBe(false);
    expect(parseFrontmatter(noDraftInput).meta.draft).toBe(false);
  });

  it("handles invalid date gracefully", () => {
    const input = `---
title: Post
date: not-a-date
---
Content.`;

    const { meta } = parseFrontmatter(input);
    expect(meta.date).toBeUndefined();
  });

  it("preserves custom frontmatter keys", () => {
    const input = `---
title: Post
author: Alice
customField: hello
tags: [ts]
---
Content.`;

    const { meta } = parseFrontmatter(input);
    expect(meta.author).toBe("Alice");
    expect(meta.customField).toBe("hello");
  });

  it("handles empty frontmatter", () => {
    const input = `---
---
Content only.`;

    const { meta, content } = parseFrontmatter(input);
    expect(meta.title).toBe("Untitled");
    expect(content.trim()).toBe("Content only.");
  });

  it("handles no frontmatter", () => {
    const input = `Just plain content without frontmatter.`;

    const { meta, content } = parseFrontmatter(input);
    expect(meta.title).toBe("Untitled");
    expect(meta.tags).toEqual([]);
    expect(meta.draft).toBe(false);
    expect(content.trim()).toBe("Just plain content without frontmatter.");
  });
});
