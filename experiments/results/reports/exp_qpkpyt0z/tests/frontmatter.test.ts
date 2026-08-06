import { describe, it, expect } from "vitest";
import {
  parseFrontmatter,
  isDraft,
  isPublishable,
  parseTags,
  parseDate,
  sortByDate,
  hasTitle,
} from "../src/frontmatter.js";

describe("parseFrontmatter", () => {
  it("parses YAML frontmatter and content", () => {
    const input = `---
title: Test
tags: [a, b]
---
Content here`;

    const { data, content } = parseFrontmatter(input);
    expect(data.title).toBe("Test");
    expect(data.tags).toEqual(["a", "b"]);
    expect(content.trim()).toBe("Content here");
  });

  it("handles empty frontmatter", () => {
    const input = `---
---
Content`;

    const { data, content } = parseFrontmatter(input);
    expect(content.trim()).toBe("Content");
    expect(data.title).toBeUndefined();
  });

  it("handles no frontmatter at all", () => {
    const input = "Just content";
    const { data, content } = parseFrontmatter(input);
    expect(content.trim()).toBe("Just content");
    expect(data.title).toBeUndefined();
  });

  it("parses date from frontmatter", () => {
    const input = `---
date: 2024-01-15
---
content`;

    const { data } = parseFrontmatter(input);
    expect(data.date).toBeDefined();
  });

  it("parses draft boolean", () => {
    const input = `---
draft: true
---
content`;

    const { data } = parseFrontmatter(input);
    expect(data.draft).toBe(true);
  });
});

describe("isDraft / isPublishable", () => {
  it("returns true for draft: true", () => {
    expect(isDraft({ title: "x", draft: true })).toBe(true);
  });

  it("returns false when draft is false", () => {
    expect(isDraft({ title: "x", draft: false })).toBe(false);
  });

  it("returns false when draft is not set", () => {
    expect(isDraft({ title: "x" })).toBe(false);
  });

  it("isPublishable is the inverse", () => {
    expect(isPublishable({ title: "x", draft: true })).toBe(false);
    expect(isPublishable({ title: "x" })).toBe(true);
  });
});

describe("hasTitle", () => {
  it("returns true for valid title", () => {
    expect(hasTitle({ title: "Hello" })).toBe(true);
  });

  it("returns false for empty string", () => {
    expect(hasTitle({ title: "" })).toBe(false);
  });

  it("returns false for missing title", () => {
    expect(hasTitle({})).toBe(false);
  });
});

describe("parseTags", () => {
  it("parses array of tags", () => {
    expect(parseTags({ tags: ["foo", "BAR"] })).toEqual(["foo", "bar"]);
  });

  it("parses comma-separated string", () => {
    expect(parseTags({ tags: "foo, bar, baz" })).toEqual(["foo", "bar", "baz"]);
  });

  it("returns empty array when no tags", () => {
    expect(parseTags({})).toEqual([]);
  });

  it("returns empty array for empty tags", () => {
    expect(parseTags({ tags: [] })).toEqual([]);
  });

  it("filters non-string entries", () => {
    expect(parseTags({ tags: ["foo", 123, "bar"] as unknown[] } as any)).toEqual(["foo", "bar"]);
  });
});

describe("parseDate", () => {
  it("parses valid date string", () => {
    const d = parseDate({ date: "2024-01-15" });
    expect(d).toBeInstanceOf(Date);
    expect(d!.getFullYear()).toBe(2024);
  });

  it("returns null for missing date", () => {
    expect(parseDate({})).toBeNull();
  });

  it("returns null for invalid date string", () => {
    expect(parseDate({ date: "not-a-date" })).toBeNull();
  });
});

describe("sortByDate", () => {
  it("sorts descending by default", () => {
    const items = [
      { frontmatter: { date: "2024-01-01" } },
      { frontmatter: { date: "2024-03-01" } },
      { frontmatter: { date: "2024-02-01" } },
    ];
    const sorted = sortByDate(items);
    expect(sorted[0].frontmatter.date).toBe("2024-03-01");
    expect(sorted[2].frontmatter.date).toBe("2024-01-01");
  });

  it("sorts ascending when desc=false", () => {
    const items = [
      { frontmatter: { date: "2024-03-01" } },
      { frontmatter: { date: "2024-01-01" } },
    ];
    const sorted = sortByDate(items, false);
    expect(sorted[0].frontmatter.date).toBe("2024-01-01");
  });
});
