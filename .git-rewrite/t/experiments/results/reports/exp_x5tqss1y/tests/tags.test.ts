import { describe, it, expect } from "vitest";
import { buildTagIndex } from "../src/tags.js";
import { Page } from "../src/types.js";

function page(title: string, tags: string[]): Page {
  return {
    frontmatter: { title, tags },
    html: "",
    content: "",
    raw: "",
    slug: title.toLowerCase(),
    sourcePath: "",
    outputPath: "",
  };
}

describe("buildTagIndex", () => {
  it("groups pages by tags", () => {
    const pages = [
      page("Post A", ["js", "css"]),
      page("Post B", ["js"]),
      page("Post C", ["css", "html"]),
    ];
    const result = buildTagIndex(pages);
    expect(result).toHaveLength(3);

    const byTag = Object.fromEntries(result.map((t) => [t.tag, t.pages.length]));
    expect(byTag["css"]).toBe(2);
    expect(byTag["html"]).toBe(1);
    expect(byTag["js"]).toBe(2);
  });

  it("returns empty array when no pages have tags", () => {
    const pages = [page("No tags", [])];
    expect(buildTagIndex(pages)).toEqual([]);
  });

  it("sorts tags alphabetically", () => {
    const pages = [
      page("X", ["z", "a", "m"]),
    ];
    const result = buildTagIndex(pages);
    expect(result.map((t) => t.tag)).toEqual(["a", "m", "z"]);
  });
});
