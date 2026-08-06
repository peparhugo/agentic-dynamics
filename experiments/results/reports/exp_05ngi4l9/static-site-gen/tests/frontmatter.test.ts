import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { parseFrontmatter, slugify, buildTagIndex, formatDate } from "../src/frontmatter.js";
import type { Post, Frontmatter } from "../src/types.js";

describe("parseFrontmatter", () => {
  it("parses title, date, tags, and draft from YAML frontmatter", () => {
    const input = `---
title: Test Post
date: 2025-06-01
tags:
  - tech
  - js
draft: false
---
Some content here.`;

    const result = parseFrontmatter(input);
    assert.equal(result.frontmatter.title, "Test Post");
    assert.ok(result.frontmatter.date instanceof Date);
    assert.equal((result.frontmatter.date as Date).toISOString().slice(0, 10), "2025-06-01");
    assert.deepEqual(result.frontmatter.tags, ["tech", "js"]);
    assert.equal(result.frontmatter.draft, false);
    assert.ok(result.content.includes("Some content here"));
  });

  it("throws if title is missing", () => {
    const input = `---
date: 2025-01-01
---
Content`;
    assert.throws(() => parseFrontmatter(input), /title/);
  });

  it("handles comma-separated tags strings", () => {
    const input = `---
title: Post
tags: a, b, c
---
Content`;
    const result = parseFrontmatter(input);
    assert.deepEqual(result.frontmatter.tags, ["a", "b", "c"]);
  });

  it("defaults draft to false and tags to empty array", () => {
    const input = `---
title: Minimal
---
Content`;
    const result = parseFrontmatter(input);
    assert.equal(result.frontmatter.draft, false);
    assert.deepEqual(result.frontmatter.tags, []);
  });

  it("parses extra frontmatter fields", () => {
    const input = `---
title: Extra
author: Jane
custom: value
---
Content`;
    const result = parseFrontmatter(input);
    assert.equal((result.frontmatter as Record<string, unknown>).author, "Jane");
    assert.equal((result.frontmatter as Record<string, unknown>).custom, "value");
  });
});

describe("slugify", () => {
  it("converts title to lowercase hyphenated slug", () => {
    assert.equal(slugify("Hello World"), "hello-world");
  });

  it("removes special characters", () => {
    assert.equal(slugify("Foo & Bar!"), "foo-bar");
  });

  it("trims leading and trailing hyphens", () => {
    assert.equal(slugify("--Hello--"), "hello");
  });
});

describe("buildTagIndex", () => {
  it("groups posts by tags", () => {
    const posts = [
      { slug: "a", frontmatter: { title: "A", tags: ["js", "css"] } },
      { slug: "b", frontmatter: { title: "B", tags: ["js"] } },
      { slug: "c", frontmatter: { title: "C", tags: ["python"] } },
    ] as Post[];

    const index = buildTagIndex(posts);
    assert.equal(Object.keys(index).length, 3);
    assert.equal(index["js"].length, 2);
    assert.equal(index["css"].length, 1);
    assert.equal(index["python"].length, 1);
  });

  it("returns empty object for posts with no tags", () => {
    const posts = [
      { slug: "a", frontmatter: { title: "A", tags: [] } },
    ] as Post[];
    assert.deepEqual(buildTagIndex(posts), {});
  });
});

describe("formatDate", () => {
  it("formats date as YYYY-MM-DD", () => {
    assert.equal(formatDate(new Date("2025-06-15")), "2025-06-15");
  });
});

describe("markdown rendering", () => {
  it("renders code blocks with syntax highlighting classes", async () => {
    const { parseFrontmatter } = await import("../src/frontmatter.js");
    const { marked } = await import("marked");
    const input = `---
title: Code Post
---
\`\`\`javascript
const x = 1;
\`\`\``;
    const { content } = parseFrontmatter(input);
    const html = await marked.parse(content);
    assert.ok(html.includes("hljs"));
    assert.ok(html.includes("language-javascript"));
  });
});
