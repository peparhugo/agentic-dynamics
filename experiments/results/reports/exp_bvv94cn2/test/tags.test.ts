import { describe, it, expect } from "vitest";
import { buildTagIndexes } from "../src/tags.js";
import type { Page } from "../src/types.js";

function makePage(title: string, date: string, tags: string[], draft = false): Page {
  return {
    path: `/posts/${title.toLowerCase()}.md`,
    sourcePath: `${title.toLowerCase()}.md`,
    frontmatter: { title, date, tags, draft },
    content: "",
    html: "",
    url: `/${title.toLowerCase()}/`,
  };
}

describe("buildTagIndexes", () => {
  it("groups pages by tag", () => {
    const pages = [
      makePage("A", "2024-01-01", ["js", "css"]),
      makePage("B", "2024-02-01", ["js"]),
      makePage("C", "2024-03-01", ["css"]),
    ];

    const indexes = buildTagIndexes(pages);
    expect(indexes.length).toBe(2);
    expect(indexes[0].tag).toBe("css");
    expect(indexes[1].tag).toBe("js");
    expect(indexes[0].pages.length).toBe(2);
    expect(indexes[1].pages.length).toBe(2);
  });

  it("excludes draft pages", () => {
    const pages = [
      makePage("A", "2024-01-01", ["js"]),
      makePage("B", "2024-02-01", ["js"], true),
    ];

    const indexes = buildTagIndexes(pages);
    expect(indexes[0].pages.length).toBe(1);
    expect(indexes[0].pages[0].frontmatter.title).toBe("A");
  });

  it("handles pages without tags", () => {
    const pages = [
      makePage("A", "2024-01-01", []),
      makePage("B", "2024-02-01", ["js"]),
    ];

    const indexes = buildTagIndexes(pages);
    expect(indexes.length).toBe(1);
    expect(indexes[0].tag).toBe("js");
  });

  it("sorts pages by date descending within each tag", () => {
    const pages = [
      makePage("Old", "2024-01-01", ["js"]),
      makePage("New", "2024-06-01", ["js"]),
    ];

    const indexes = buildTagIndexes(pages);
    expect(indexes[0].pages[0].frontmatter.title).toBe("New");
    expect(indexes[0].pages[1].frontmatter.title).toBe("Old");
  });

  it("returns empty array for no tagged pages", () => {
    const pages = [makePage("A", "2024-01-01", [])];
    expect(buildTagIndexes(pages)).toEqual([]);
  });
});
