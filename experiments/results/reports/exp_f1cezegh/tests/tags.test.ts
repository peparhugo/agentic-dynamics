import { describe, it, expect } from "vitest";
import { generateTagIndexes, generateTagPageData } from "../src/tags";
import { Page } from "../src/types";
import { parseFrontmatter } from "../src/frontmatter";

function makePage(file: string, raw: string): Page {
  const { meta, content } = parseFrontmatter(raw);
  return { path: file, url: file.replace(".md", ".html"), meta, content, raw };
}

describe("generateTagIndexes", () => {
  it("groups pages by tags", () => {
    const pages: Page[] = [
      makePage(
        "post1.md",
        `---
title: TypeScript Guide
date: 2024-01-15
tags: [typescript, tutorial]
---
Content.`
      ),
      makePage(
        "post2.md",
        `---
title: JS Tips
date: 2024-02-20
tags: [javascript, tutorial]
---
Content.`
      ),
      makePage(
        "post3.md",
        `---
title: Rust Intro
date: 2024-03-10
tags: [rust]
---
Content.`
      ),
    ];

    const indexes = generateTagIndexes(pages);

    expect(indexes.size).toBe(4);
    expect(indexes.get("typescript")!.length).toBe(1);
    expect(indexes.get("tutorial")!.length).toBe(2);
    expect(indexes.get("javascript")!.length).toBe(1);
    expect(indexes.get("rust")!.length).toBe(1);
  });

  it("excludes draft pages from tag indexes", () => {
    const pages: Page[] = [
      makePage(
        "post1.md",
        `---
title: Public
tags: [ts]
---
Content.`
      ),
      makePage(
        "draft.md",
        `---
title: Draft
tags: [ts]
draft: true
---
Hidden.`
      ),
    ];

    const indexes = generateTagIndexes(pages);
    expect(indexes.get("ts")!.length).toBe(1);
  });

  it("returns empty map for no pages", () => {
    const indexes = generateTagIndexes([]);
    expect(indexes.size).toBe(0);
  });
});

describe("generateTagPageData", () => {
  it("generates tag page data", () => {
    const pages: Page[] = [
      makePage(
        "post1.md",
        `---
title: Post One
date: 2024-01-15
tags: [ts]
---
Content.`
      ),
    ];

    const data = generateTagPageData("typescript", pages, "My Site");

    expect(data.title).toBe("Tag: typescript");
    expect(data.tag).toBe("typescript");
    expect(data.siteTitle).toBe("My Site");
    expect(Array.isArray(data.pages)).toBe(true);
    expect((data.pages as Array<unknown>).length).toBe(1);
  });
});
