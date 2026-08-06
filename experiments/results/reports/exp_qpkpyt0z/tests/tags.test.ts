import { describe, it, expect } from "vitest";
import { buildTagIndex } from "../src/tags.js";
import type { Page } from "../src/types.js";

function makePage(title: string, tags: string[], date = "2024-01-01", draft = false): Page {
  return {
    path: "",
    frontmatter: { title, date, tags },
    content: "",
    html: "",
    url: `/${title}/index.html`,
    isDraft: draft,
  };
}

describe("buildTagIndex", () => {
  it("builds tag index from pages", () => {
    const pages: Page[] = [
      makePage("Post A", ["javascript", "web"]),
      makePage("Post B", ["javascript"]),
      makePage("Post C", ["web"]),
    ];
    const tags = buildTagIndex(pages);

    expect(tags).toHaveLength(2);

    const jsTag = tags.find((t) => t.name === "javascript")!;
    expect(jsTag.count).toBe(2);
    expect(jsTag.pages).toHaveLength(2);

    const webTag = tags.find((t) => t.name === "web")!;
    expect(webTag.count).toBe(2);
  });

  it("excludes draft pages from tags", () => {
    const pages: Page[] = [
      makePage("Pub", ["javascript"], "2024-01-01", false),
      makePage("Draft", ["javascript"], "2024-01-01", true),
    ];
    const tags = buildTagIndex(pages);

    const jsTag = tags.find((t) => t.name === "javascript")!;
    expect(jsTag.count).toBe(1);
  });

  it("sorts tags by count descending", () => {
    const pages: Page[] = [
      makePage("A", ["rare"]),
      makePage("B", ["common"]),
      makePage("C", ["common"]),
      makePage("D", ["common"]),
    ];
    const tags = buildTagIndex(pages);
    expect(tags[0].name).toBe("common");
    expect(tags[0].count).toBe(3);
    expect(tags[1].name).toBe("rare");
  });

  it("handles pages with no tags", () => {
    const pages: Page[] = [
      makePage("A", []),
      makePage("B", []),
    ];
    const tags = buildTagIndex(pages);
    expect(tags).toHaveLength(0);
  });

  it("handles empty page list", () => {
    const tags = buildTagIndex([]);
    expect(tags).toEqual([]);
  });
});
