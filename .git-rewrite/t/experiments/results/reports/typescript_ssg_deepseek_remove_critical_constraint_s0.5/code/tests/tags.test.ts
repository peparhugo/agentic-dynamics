import { describe, it, expect } from "vitest";
import { buildTagData } from "../src/tags";
import { Page } from "../src/types";

function makePage(title: string, tags: string[], date?: string): Page {
  return {
    frontmatter: { title, tags, date },
    content: "",
    html: "",
    slug: title.toLowerCase().replace(/\s+/g, "-"),
    sourcePath: "",
  };
}

describe("buildTagData", () => {
  it("returns empty array for pages with no tags", () => {
    const pages = [makePage("No Tags", [])];
    expect(buildTagData(pages)).toEqual([]);
  });

  it("groups pages by tag", () => {
    const pages = [
      makePage("Post 1", ["javascript", "web"]),
      makePage("Post 2", ["javascript"]),
    ];
    const tags = buildTagData(pages);
    expect(tags).toHaveLength(2);

    const js = tags.find((t) => t.tag === "javascript");
    expect(js?.pages).toHaveLength(2);

    const web = tags.find((t) => t.tag === "web");
    expect(web?.pages).toHaveLength(1);
  });

  it("sorts tags alphabetically", () => {
    const pages = [
      makePage("Post", ["beta"]),
      makePage("Post", ["alpha"]),
    ];
    const tags = buildTagData(pages);
    expect(tags[0].tag).toBe("alpha");
    expect(tags[1].tag).toBe("beta");
  });

  it("sorts pages within a tag by date descending", () => {
    const pages = [
      makePage("Older", ["go"], "2024-01-01"),
      makePage("Newer", ["go"], "2024-06-01"),
    ];
    const tags = buildTagData(pages);
    const go = tags.find((t) => t.tag === "go");
    expect(go?.pages[0].frontmatter.title).toBe("Newer");
    expect(go?.pages[1].frontmatter.title).toBe("Older");
  });

  it("normalizes tags to lowercase", () => {
    const pages = [
      makePage("Post", ["JavaScript"]),
      makePage("Post", ["javascript"]),
    ];
    const tags = buildTagData(pages);
    expect(tags).toHaveLength(1);
    expect(tags[0].tag).toBe("javascript");
  });
});
