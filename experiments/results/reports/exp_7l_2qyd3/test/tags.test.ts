import { describe, it, expect } from "vitest";
import { buildTagIndex, generateTagPages } from "../src/tags.js";
import type { Page } from "../src/types.js";

const makePage = (
  title: string,
  tags: string[],
  slug: string = title.toLowerCase()
): Page => ({
  frontmatter: { title, tags },
  content: `<p>${title}</p>`,
  slug,
  sourcePath: `${slug}.md`,
  outputPath: `out/${slug}/index.html`,
  html: "",
});

describe("buildTagIndex", () => {
  it("builds index from pages with tags", () => {
    const pages = [
      makePage("Post 1", ["typescript", "node"]),
      makePage("Post 2", ["typescript"]),
      makePage("Post 3", ["css"]),
    ];

    const idx = buildTagIndex(pages);
    expect(idx.get("typescript")!.count).toBe(2);
    expect(idx.get("node")!.count).toBe(1);
    expect(idx.get("css")!.count).toBe(1);
  });

  it("handles pages with no tags", () => {
    const pages = [makePage("No Tags", [])];
    const idx = buildTagIndex(pages);
    expect(idx.size).toBe(0);
  });

  it("handles missing tags field", () => {
    const page: Page = {
      frontmatter: { title: "Missing Tags" },
      content: "",
      slug: "missing",
      sourcePath: "missing.md",
      outputPath: "",
      html: "",
    };
    const idx = buildTagIndex([page]);
    expect(idx.size).toBe(0);
  });

  it("includes page references in tag info", () => {
    const pages = [makePage("T1", ["rust"])];
    const idx = buildTagIndex(pages);
    const info = idx.get("rust")!;
    expect(info.pages).toHaveLength(1);
    expect(info.pages[0].frontmatter.title).toBe("T1");
  });
});

describe("generateTagPages", () => {
  it("generates HTML for each tag", () => {
    const pages = [
      makePage("A1", ["go"]),
      makePage("A2", ["python"]),
    ];
    const idx = buildTagIndex(pages);

    const renderTagPage = (info: ReturnType<typeof buildTagIndex> extends Map<string, infer T> ? T : never, _all: Page[]) =>
      `<h1>Tag: ${info.tag} (${info.count})</h1>`;

    const result = generateTagPages(idx, pages, renderTagPage);
    expect(result.size).toBe(2);
    expect(result.get("tags/go/index.html")).toContain("Tag: go (1)");
    expect(result.get("tags/python/index.html")).toContain("Tag: python (1)");
  });
});
