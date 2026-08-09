import { describe, it, expect } from "vitest";
import { buildTagIndex, tagIndexToArray } from "../src/tags.js";
import type { Page } from "../src/types.js";

function makePage(tags: string[], draft = false): Page {
  return {
    frontmatter: { title: "P", tags },
    content: "",
    html: "",
    slug: "p",
    sourcePath: "/src/p.md",
    outputPath: "/out/p.html",
    isDraft: draft,
  };
}

describe("buildTagIndex", () => {
  it("groups pages by tag", () => {
    const pages = [
      makePage(["js", "ts"]),
      makePage(["ts", "css"]),
      makePage(["js"]),
    ];
    const index = buildTagIndex(pages);
    expect(index.get("js")?.length).toBe(2);
    expect(index.get("ts")?.length).toBe(2);
    expect(index.get("css")?.length).toBe(1);
  });

  it("excludes draft pages", () => {
    const pages = [
      makePage(["js"], false),
      makePage(["js"], true),
    ];
    const index = buildTagIndex(pages);
    expect(index.get("js")?.length).toBe(1);
  });

  it("returns empty map for no tags", () => {
    const pages = [makePage([]), makePage([])];
    const index = buildTagIndex(pages);
    expect(index.size).toBe(0);
  });

  it("handles pages with undefined tags", () => {
    const page: Page = {
      frontmatter: { title: "No Tags" },
      content: "",
      html: "",
      slug: "notags",
      sourcePath: "/src/notags.md",
      outputPath: "/out/notags.html",
      isDraft: false,
    };
    const index = buildTagIndex([page]);
    expect(index.size).toBe(0);
  });
});

describe("tagIndexToArray", () => {
  it("converts map to array of TagIndex", () => {
    const map = new Map();
    map.set("js", [makePage(["js"])]);
    map.set("ts", [makePage(["ts"])]);
    const arr = tagIndexToArray(map);
    expect(arr.length).toBe(2);
    expect(arr[0].tag).toBeDefined();
    expect(arr[0].pages.length).toBe(1);
  });
});
