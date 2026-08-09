import { describe, it, expect } from "vitest";
import { parseMarkdown, getPublishedPages, sortByDate } from "../src/parser.js";
import type { Page } from "../src/types.js";

describe("parseMarkdown", () => {
  it("parses title from frontmatter", () => {
    const md = `---
title: Hello World
---
Some content.`;

    const result = parseMarkdown(md, "hello.md");
    expect(result.frontmatter.title).toBe("Hello World");
  });

  it("parses date from frontmatter", () => {
    const md = `---
title: Test
date: 2024-01-15
---
Content`;

    const result = parseMarkdown(md, "test.md");
    expect(result.frontmatter.date).toBe("2024-01-15");
  });

  it("parses tags as array", () => {
    const md = `---
title: Tagged
tags:
  - typescript
  - nodejs
---
Content`;

    const result = parseMarkdown(md, "tagged.md");
    expect(result.frontmatter.tags).toEqual(["typescript", "nodejs"]);
  });

  it("parses draft flag", () => {
    const md = `---
title: Draft Post
draft: true
---
Secret stuff`;

    const result = parseMarkdown(md, "draft.md");
    expect(result.frontmatter.draft).toBe(true);
  });

  it("defaults draft to false when not set", () => {
    const md = `---
title: Published
---
Public`;

    const result = parseMarkdown(md, "pub.md");
    expect(result.frontmatter.draft).toBe(false);
  });

  it("defaults title to Untitled when missing", () => {
    const md = `---
tags: [a]
---
No title`;

    const result = parseMarkdown(md, "notitle.md");
    expect(result.frontmatter.title).toBe("Untitled");
  });

  it("converts markdown content to HTML", () => {
    const md = `---
title: MD Test
---
**bold** and *italic*`;

    const result = parseMarkdown(md, "mdtest.md");
    expect(result.content).toContain("<strong>bold</strong>");
    expect(result.content).toContain("<em>italic</em>");
  });

  it("generates slug from source path", () => {
    const md = `---
title: Deep
---
Content`;

    const result = parseMarkdown(md, "blog/deep.md");
    expect(result.slug).toBe("blog/deep");
  });

  it("handles index.md as directory index", () => {
    const md = `---
title: Index Page
---
Index`;

    const result = parseMarkdown(md, "index.md");
    expect(result.slug).toBe("");
  });

  it("handles code blocks with language", () => {
    const md = `---
title: Code
---
\`\`\`typescript
const x = 1;
\`\`\``;

    const result = parseMarkdown(md, "code.md");
    expect(result.content).toContain("<pre>");
    expect(result.content).toContain("<code");
    expect(result.content).toContain("language-typescript");
  });

  it("handles code blocks without language", () => {
    const md = `---
title: NoLang
---
\`\`\`
plain code
\`\`\``;

    const result = parseMarkdown(md, "nolang.md");
    expect(result.content).toContain("<code>plain code");
  });
});

describe("getPublishedPages", () => {
  it("filters out draft pages", () => {
    const pages: Page[] = [
      {
        frontmatter: { title: "A", draft: false },
        content: "",
        slug: "a",
        sourcePath: "a.md",
        outputPath: "",
        html: "",
      },
      {
        frontmatter: { title: "B", draft: true },
        content: "",
        slug: "b",
        sourcePath: "b.md",
        outputPath: "",
        html: "",
      },
    ];

    const result = getPublishedPages(pages);
    expect(result).toHaveLength(1);
    expect(result[0].frontmatter.title).toBe("A");
  });
});

describe("sortByDate", () => {
  it("sorts pages by date descending", () => {
    const pages: Page[] = [
      {
        frontmatter: { title: "Old", date: "2023-01-01" },
        content: "",
        slug: "old",
        sourcePath: "",
        outputPath: "",
        html: "",
      },
      {
        frontmatter: { title: "New", date: "2024-06-15" },
        content: "",
        slug: "new",
        sourcePath: "",
        outputPath: "",
        html: "",
      },
      {
        frontmatter: { title: "Mid", date: "2024-01-01" },
        content: "",
        slug: "mid",
        sourcePath: "",
        outputPath: "",
        html: "",
      },
    ];

    const sorted = sortByDate(pages);
    expect(sorted[0].frontmatter.title).toBe("New");
    expect(sorted[1].frontmatter.title).toBe("Mid");
    expect(sorted[2].frontmatter.title).toBe("Old");
  });
});
