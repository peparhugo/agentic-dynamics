import { describe, it, expect } from "vitest";
import { parseFrontmatter, sourceToOutputPath, sourceToUrl, createPage } from "../src/frontmatter.js";
import path from "node:path";

describe("parseFrontmatter", () => {
  it("parses title from frontmatter", () => {
    const raw = `---
title: Hello World
---
Body content`;
    const { data, content } = parseFrontmatter(raw);
    expect(data.title).toBe("Hello World");
    expect(content.trim()).toBe("Body content");
  });

  it("applies defaults for missing fields", () => {
    const raw = `---
title: Minimal
---`;
    const { data } = parseFrontmatter(raw);
    expect(data.title).toBe("Minimal");
    expect(data.draft).toBe(false);
    expect(data.tags).toEqual([]);
  });

  it("parses tags as array", () => {
    const raw = `---
title: Tagged
tags:
  - js
  - ts
---`;
    const { data } = parseFrontmatter(raw);
    expect(data.tags).toEqual(["js", "ts"]);
  });

  it("parses comma-separated tag string", () => {
    const raw = `---
title: Tagged
tags: js, ts, css
---`;
    const { data } = parseFrontmatter(raw);
    expect(data.tags).toEqual(["js", "ts", "css"]);
  });

  it("parses draft flag", () => {
    const raw = `---
title: Draft Post
draft: true
---`;
    const { data } = parseFrontmatter(raw);
    expect(data.draft).toBe(true);
  });

  it("parses date field", () => {
    const raw = `---
title: Dated
date: 2024-01-15
---`;
    const { data } = parseFrontmatter(raw);
    expect(data.date).toBe("2024-01-15");
  });

  it("parses custom fields", () => {
    const raw = `---
title: Custom
author: John
rating: 5
---`;
    const { data } = parseFrontmatter(raw);
    expect(data.author).toBe("John");
    expect(data.rating).toBe(5);
  });

  it("handles no frontmatter gracefully", () => {
    const raw = "Just content";
    const { data, content } = parseFrontmatter(raw);
    expect(data.title).toBe("Untitled");
    expect(data.draft).toBe(false);
    expect(content.trim()).toBe("Just content");
  });

  it("handles empty file", () => {
    const { data, content } = parseFrontmatter("");
    expect(data.title).toBe("Untitled");
    expect(content).toBe("");
  });
});

describe("sourceToOutputPath", () => {
  const sourceDir = "/src/content";
  const outputDir = "/src/public";

  it("converts .md to directory-based .html path", () => {
    const result = sourceToOutputPath(
      path.join(sourceDir, "blog/hello.md"),
      sourceDir,
      outputDir,
    );
    expect(result).toBe(path.join(outputDir, "blog", "hello", "index.html"));
  });

  it("handles index.md as root index.html", () => {
    const result = sourceToOutputPath(
      path.join(sourceDir, "index.md"),
      sourceDir,
      outputDir,
    );
    expect(result).toBe(path.join(outputDir, "index.html"));
  });
});

describe("sourceToUrl", () => {
  const sourceDir = "/src/content";

  it("generates clean URL from file path", () => {
    const result = sourceToUrl(
      path.join(sourceDir, "blog/hello.md"),
      sourceDir,
    );
    expect(result).toBe("/blog/hello/");
  });

  it("handles index.md as root URL", () => {
    const result = sourceToUrl(
      path.join(sourceDir, "index.md"),
      sourceDir,
    );
    expect(result).toBe("/");
  });

  it("handles index files in subdirectories", () => {
    const result = sourceToUrl(
      path.join(sourceDir, "blog/index.md"),
      sourceDir,
    );
    expect(result).toBe("/blog/");
  });
});

describe("createPage", () => {
  const sourceDir = "/src/content";
  const outputDir = "/src/public";

  it("creates a page with all metadata", () => {
    const raw = `---
title: Test
date: 2024-01-15
tags:
  - js
draft: false
---
Hello world`;

    const page = createPage(
      path.join(sourceDir, "blog/test.md"),
      sourceDir,
      outputDir,
      raw,
    );

    expect(page.frontmatter.title).toBe("Test");
    expect(page.frontmatter.date).toBe("2024-01-15");
    expect(page.tags).toEqual(["js"]);
    expect(page.isDraft).toBe(false);
    expect(page.content.trim()).toBe("Hello world");
    expect(page.html).toBe("");
    expect(page.url).toBe("/blog/test/");
  });
});
