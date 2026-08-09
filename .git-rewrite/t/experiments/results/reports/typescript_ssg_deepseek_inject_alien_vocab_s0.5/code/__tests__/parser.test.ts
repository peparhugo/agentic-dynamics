import { describe, it, expect } from "vitest";
import { parseFrontmatter } from "../src/lib/parser";

describe("parseFrontmatter", () => {
  it("parses title, date, and tags from YAML frontmatter", () => {
    const input = `---
title: Hello World
date: 2024-01-15
tags:
  - typescript
  - ssg
---

This is the body.`;

    const result = parseFrontmatter(input);
    expect(result.attributes.title).toBe("Hello World");
    expect(result.attributes.date).toBe("2024-01-15");
    expect(result.attributes.tags).toEqual(["typescript", "ssg"]);
    expect(result.body).toBe("This is the body.");
  });

  it("parses draft flag", () => {
    const input = `---
title: Draft Post
draft: true
---

Content`;

    const result = parseFrontmatter(input);
    expect(result.attributes.draft).toBe(true);
  });

  it("parses layout field", () => {
    const input = `---
title: Custom Layout
layout: fancy
---

Body`;

    const result = parseFrontmatter(input);
    expect(result.attributes.layout).toBe("fancy");
  });

  it("returns raw body when no frontmatter exists", () => {
    const input = "Just markdown body, no frontmatter.";

    const result = parseFrontmatter(input);
    expect(result.attributes.title).toBe("");
    expect(result.body).toBe("Just markdown body, no frontmatter.");
  });

  it("handles empty frontmatter", () => {
    const input = `---
---

Body`;

    const result = parseFrontmatter(input);
    expect(result.attributes.title).toBe("");
    expect(result.body).toBe("Body");
  });

  it("preserves extra frontmatter fields", () => {
    const input = `---
title: Test
custom_field: value123
---

Body`;

    const result = parseFrontmatter(input);
    expect(result.attributes.custom_field).toBe("value123");
  });

  it("handles frontmatter with only opening dashes", () => {
    const input = `---
title: Incomplete`;

    const result = parseFrontmatter(input);
    expect(result.attributes.title).toBe("");
  });
});
